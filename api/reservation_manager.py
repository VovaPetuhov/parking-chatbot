import asyncio
import json
import logging
import threading
import uuid
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from filelock import FileLock

from api.notification_service import get_notification_service
from api.reservation_models import (ReservationCreate, ReservationResponse,
                                    ReservationStatusEnum)

logger = logging.getLogger(__name__)


class Reservation:
    def __init__(
        self,
        reservation_id: str,
        conversation_id: str,
        name: str,
        surname: str,
        car_plate: str,
        start_time: str,
        end_time: str,
        status: ReservationStatusEnum = ReservationStatusEnum.PENDING_APPROVAL,
        admin_comment: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.reservation_id = reservation_id
        self.conversation_id = conversation_id
        self.name = name
        self.surname = surname
        self.car_plate = car_plate
        self.start_time = start_time
        self.end_time = end_time
        self.status = status
        self.admin_comment = admin_comment
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()

    def to_response(self) -> ReservationResponse:
        return ReservationResponse(
            reservation_id=self.reservation_id,
            conversation_id=self.conversation_id,
            name=self.name,
            surname=self.surname,
            car_plate=self.car_plate,
            start_time=self.start_time,
            end_time=self.end_time,
            status=self.status,
            created_at=self.created_at,
            updated_at=self.updated_at,
            admin_comment=self.admin_comment,
        )

    def is_expired(self, ttl_seconds: int) -> bool:
        if self.status != ReservationStatusEnum.PENDING_APPROVAL:
            return False
        age = datetime.now() - self.created_at
        return age.total_seconds() > ttl_seconds

    def to_dict(self) -> Dict:
        return {
            "reservation_id": self.reservation_id,
            "conversation_id": self.conversation_id,
            "name": self.name,
            "surname": self.surname,
            "car_plate": self.car_plate,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status.value,
            "admin_comment": self.admin_comment,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Reservation":
        return cls(
            reservation_id=data["reservation_id"],
            conversation_id=data["conversation_id"],
            name=data["name"],
            surname=data["surname"],
            car_plate=data["car_plate"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            status=ReservationStatusEnum(data["status"]),
            admin_comment=data.get("admin_comment"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


class ReservationManager:
    """
    Hybrid in-memory + file-based reservation storage.
    Strategy:
    - In-memory cache (OrderedDict) for fast O(1) lookups
    - File-based persistence for cross-process sharing
    - Write-through: write to both memory and file
    - Lazy loading: load from file on cache miss
    - Cache invalidation: check file mtime periodically
    Features:
    - Thread-safe with asyncio.Lock for in-memory operations
    - Process-safe with FileLock for file operations
    - Automatic expiration for pending reservations
    - Admin approval/rejection workflow
    """

    def __init__(
        self,
        pending_ttl_seconds: int = 3600,
        max_reservations: int = 10000,
        storage_dir: Optional[Path] = None,
        cache_ttl_seconds: int = 5
    ):
        self.pending_ttl_seconds = pending_ttl_seconds
        self.max_reservations = max_reservations
        self.reservations: OrderedDict[str, Reservation] = OrderedDict()
        self.memory_lock = asyncio.Lock()
        if storage_dir is None:
            storage_dir = Path("storage")
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        self.file_path = self.storage_dir / "reservations.json"
        self.lock_file = self.storage_dir / "reservations.json.lock"
        self.file_lock = FileLock(str(self.lock_file), timeout=10)
        self.cache_timestamp: Optional[datetime] = None
        self.last_file_mtime: Optional[float] = None
        self.cache_ttl_seconds = cache_ttl_seconds
        logger.info(
            f"ReservationManager initialized (Hybrid mode) "
            f"[Pending TTL: {pending_ttl_seconds}s, Max: {max_reservations}, "
            f"Storage: {self.file_path}, Cache TTL: {cache_ttl_seconds}s]"
        )

    async def _check_file_modified(self) -> bool:
        if not self.file_path.exists():
            return False
        
        current_mtime = await asyncio.to_thread(
            lambda: self.file_path.stat().st_mtime
        )
        
        if self.last_file_mtime is None:
            self.last_file_mtime = current_mtime
            return False
        
        if current_mtime > self.last_file_mtime:
            logger.debug("File modified by another process")
            self.last_file_mtime = current_mtime
            return True
        
        return False

    async def _ensure_fresh_cache(self):
        now = datetime.now()
        cache_age = (
            (now - self.cache_timestamp).total_seconds() 
            if self.cache_timestamp 
            else float('inf')
        )
        
        if cache_age > 30:
            logger.debug("Cache expired (>30s), force reload")
            await self._reload_from_file()
            self.cache_timestamp = now
            return
        
        if cache_age > self.cache_ttl_seconds:
            if await self._check_file_modified():
                logger.debug("File modified, reloading cache")
                await self._reload_from_file()
            self.cache_timestamp = now

    async def _reload_from_file(self):
        data = await asyncio.to_thread(self._load_from_file_sync)
        
        if not data:
            logger.debug("No data to load from file")
            return
        
        file_ids = set(data.keys())
        memory_ids = set(self.reservations.keys())
        
        new_ids = file_ids - memory_ids
        for res_id in new_ids:
            try:
                self.reservations[res_id] = Reservation.from_dict(data[res_id])
                logger.debug(f"Loaded new reservation from file: {res_id}")
            except Exception as e:
                logger.error(f"Failed to load reservation {res_id}: {e}")
        
        deleted_ids = memory_ids - file_ids
        for res_id in deleted_ids:
            del self.reservations[res_id]
            logger.debug(f"Removed deleted reservation: {res_id}")
        
        existing_ids = file_ids & memory_ids
        updated_count = 0
        for res_id in existing_ids:
            try:
                file_res = Reservation.from_dict(data[res_id])
                memory_res = self.reservations[res_id]
                
                if file_res.updated_at > memory_res.updated_at:
                    self.reservations[res_id] = file_res
                    updated_count += 1
                    logger.debug(f"Updated reservation from file: {res_id}")
            except Exception as e:
                logger.error(f"Failed to update reservation {res_id}: {e}")
        
        logger.debug(
            f"Reload complete: {len(new_ids)} new, {len(deleted_ids)} deleted, "
            f"{updated_count} updated"
        )

    def _load_from_file_sync(self) -> Dict:
        with self.file_lock:
            if not self.file_path.exists():
                return {}
            
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.debug(f"Loaded {len(data)} reservations from file")
                    return data
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse reservations file: {e}")
                return {}
            except Exception as e:
                logger.error(f"Failed to load reservations file: {e}")
                return {}

    async def _save_to_file(self):
        await asyncio.to_thread(self._save_to_file_sync)

    def _save_to_file_sync(self):
        with self.file_lock:
            try:
                if self.file_path.exists():
                    try:
                        with open(self.file_path, 'r', encoding='utf-8') as f:
                            existing_data = json.load(f)
                    except (json.JSONDecodeError, Exception) as e:
                        logger.warning(f"Failed to read existing file, starting fresh: {e}")
                        existing_data = {}
                else:
                    existing_data = {}
                
                for res_id, reservation in self.reservations.items():
                    existing_data[res_id] = reservation.to_dict()
                
                temp_file = self.file_path.with_suffix('.tmp')
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(existing_data, f, indent=2, ensure_ascii=False)
                temp_file.replace(self.file_path)
                self.last_file_mtime = self.file_path.stat().st_mtime
                
                logger.debug(f"Saved {len(existing_data)} reservations to file")
            except Exception as e:
                logger.error(f"Failed to save reservations to file: {e}", exc_info=True)

    async def create_reservation(
        self, data: ReservationCreate
    ) -> ReservationResponse:
        async with self.memory_lock:
            return await self._create_reservation_internal(data)

    def create_reservation_sync(self, data: ReservationCreate) -> ReservationResponse:
        result = self._create_reservation_internal_sync(data)
        self._save_to_file_sync()
        
        return result

    async def _create_reservation_internal(self, data: ReservationCreate) -> ReservationResponse:
        reservation_id = f"res_{uuid.uuid4().hex[:12]}"

        if len(self.reservations) >= self.max_reservations:
            oldest_id = next(iter(self.reservations))
            logger.warning(
                f"Max reservations ({self.max_reservations}) reached, "
                f"evicting oldest: {oldest_id}"
            )
            self.reservations.pop(oldest_id)

        reservation = Reservation(
            reservation_id=reservation_id,
            conversation_id=data.conversation_id,
            name=data.name,
            surname=data.surname,
            car_plate=data.car_plate,
            start_time=data.start_time,
            end_time=data.end_time,
        )

        self.reservations[reservation_id] = reservation
        self.reservations.move_to_end(reservation_id)

        logger.info(
            f"Created reservation {reservation_id} for {data.name} {data.surname}, "
            f"car {data.car_plate}, period {data.start_time} - {data.end_time}"
        )

        await self._save_to_file()
        self._schedule_email_notification(reservation)

        return reservation.to_response()

    def _create_reservation_internal_sync(self, data: ReservationCreate) -> ReservationResponse:
        """Internal sync reservation creation (no file save, caller must save)"""
        reservation_id = f"res_{uuid.uuid4().hex[:12]}"

        if len(self.reservations) >= self.max_reservations:
            oldest_id = next(iter(self.reservations))
            logger.warning(
                f"Max reservations ({self.max_reservations}) reached, "
                f"evicting oldest: {oldest_id}"
            )
            self.reservations.pop(oldest_id)

        reservation = Reservation(
            reservation_id=reservation_id,
            conversation_id=data.conversation_id,
            name=data.name,
            surname=data.surname,
            car_plate=data.car_plate,
            start_time=data.start_time,
            end_time=data.end_time,
        )

        self.reservations[reservation_id] = reservation
        self.reservations.move_to_end(reservation_id)

        logger.info(
            f"Created reservation {reservation_id} for {data.name} {data.surname}, "
            f"car {data.car_plate}, period {data.start_time} - {data.end_time}"
        )

        self._schedule_email_notification(reservation)

        return reservation.to_response()

    def _schedule_email_notification(self, reservation: Reservation) -> None:
        try:
            notification_service = get_notification_service()

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    notification_service.send_new_reservation_notification(
                        reservation_id=reservation.reservation_id,
                        name=reservation.name,
                        surname=reservation.surname,
                        car_plate=reservation.car_plate,
                        start_time=reservation.start_time,
                        end_time=reservation.end_time,
                        conversation_id=reservation.conversation_id
                    )
                )
                logger.debug(f"Email notification task created for {reservation.reservation_id}")
            except RuntimeError:

                def send_email_sync():
                    """Run email sending in a new event loop in background thread"""
                    try:
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        new_loop.run_until_complete(
                            notification_service.send_new_reservation_notification(
                                reservation_id=reservation.reservation_id,
                                name=reservation.name,
                                surname=reservation.surname,
                                car_plate=reservation.car_plate,
                                start_time=reservation.start_time,
                                end_time=reservation.end_time,
                                conversation_id=reservation.conversation_id
                            )
                        )
                        new_loop.close()
                    except Exception as e:
                        logger.error(f"Background email sending failed: {e}", exc_info=True)

                # Start in background thread (daemon so it doesn't block shutdown)
                thread = threading.Thread(target=send_email_sync, daemon=True)
                thread.start()
                logger.debug(f"Email notification thread started for {reservation.reservation_id}")

        except Exception as e:
            logger.error(
                f"Failed to schedule email notification for {reservation.reservation_id}: {e}",
                exc_info=True
            )

    async def get_reservation(
        self, reservation_id: str
    ) -> Optional[ReservationResponse]:
        async with self.memory_lock:
            await self._ensure_fresh_cache()
            
            reservation = self.reservations.get(reservation_id)
            if not reservation:
                return None

            if reservation.is_expired(self.pending_ttl_seconds):
                logger.info(
                    f"Reservation {reservation_id} expired, marking as EXPIRED"
                )
                reservation.status = ReservationStatusEnum.EXPIRED
                reservation.updated_at = datetime.now()
                await self._save_to_file()

            return reservation.to_response()

    async def get_pending_reservations(self) -> List[ReservationResponse]:
        async with self.memory_lock:
            await self._ensure_fresh_cache()
            
            await self._cleanup_expired()
            pending = [
                res.to_response()
                for res in self.reservations.values()
                if res.status == ReservationStatusEnum.PENDING_APPROVAL
            ]
            return pending

    async def get_all_reservations(self) -> List[ReservationResponse]:
        async with self.memory_lock:
            await self._ensure_fresh_cache()
            
            await self._cleanup_expired()
            return [res.to_response() for res in self.reservations.values()]

    async def approve_reservation(
        self, reservation_id: str, comment: Optional[str] = None
    ) -> Optional[ReservationResponse]:
        async with self.memory_lock:
            await self._ensure_fresh_cache()
            
            reservation = self.reservations.get(reservation_id)
            if not reservation:
                logger.warning(f"Reservation {reservation_id} not found for approval")
                return None

            if reservation.status != ReservationStatusEnum.PENDING_APPROVAL:
                logger.warning(
                    f"Reservation {reservation_id} is not pending "
                    f"(status: {reservation.status})"
                )
                return None

            reservation.status = ReservationStatusEnum.APPROVED
            reservation.admin_comment = comment
            reservation.updated_at = datetime.now()

            logger.info(f"Approved reservation {reservation_id}")
            
            await self._save_to_file()
            
            return reservation.to_response()

    async def reject_reservation(
        self, reservation_id: str, comment: Optional[str] = None
    ) -> Optional[ReservationResponse]:
        async with self.memory_lock:
            await self._ensure_fresh_cache()
            
            reservation = self.reservations.get(reservation_id)
            if not reservation:
                logger.warning(f"Reservation {reservation_id} not found for rejection")
                return None

            if reservation.status != ReservationStatusEnum.PENDING_APPROVAL:
                logger.warning(
                    f"Reservation {reservation_id} is not pending "
                    f"(status: {reservation.status})"
                )
                return None

            reservation.status = ReservationStatusEnum.REJECTED
            reservation.admin_comment = comment
            reservation.updated_at = datetime.now()

            logger.info(f"Rejected reservation {reservation_id}")
            
            await self._save_to_file()
            
            return reservation.to_response()

    async def get_reservation_by_conversation(
        self, conversation_id: str
    ) -> Optional[ReservationResponse]:
        async with self.memory_lock:
            await self._ensure_fresh_cache()
            
            for res in reversed(self.reservations.values()):
                if res.conversation_id == conversation_id:
                    if res.is_expired(self.pending_ttl_seconds):
                        res.status = ReservationStatusEnum.EXPIRED
                        res.updated_at = datetime.now()
                        await self._save_to_file()
                    return res.to_response()
            return None

    async def _cleanup_expired(self) -> None:
        expired_count = 0
        for reservation in self.reservations.values():
            if reservation.is_expired(self.pending_ttl_seconds):
                reservation.status = ReservationStatusEnum.EXPIRED
                reservation.updated_at = datetime.now()
                expired_count += 1

        if expired_count > 0:
            logger.info(f"Marked {expired_count} reservations as EXPIRED")
            await self._save_to_file()

    async def cleanup_task(self) -> None:
        logger.info("Starting reservation cleanup task")
        while True:
            try:
                await asyncio.sleep(300)
                async with self.memory_lock:
                    await self._cleanup_expired()
            except asyncio.CancelledError:
                logger.info("Reservation cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in reservation cleanup task: {e}", exc_info=True)

    def get_stats(self) -> Dict[str, int]:
        stats = {
            "total": len(self.reservations),
            "pending": 0,
            "approved": 0,
            "rejected": 0,
            "expired": 0,
        }

        for res in self.reservations.values():
            if res.status == ReservationStatusEnum.PENDING_APPROVAL:
                stats["pending"] += 1
            elif res.status == ReservationStatusEnum.APPROVED:
                stats["approved"] += 1
            elif res.status == ReservationStatusEnum.REJECTED:
                stats["rejected"] += 1
            elif res.status == ReservationStatusEnum.EXPIRED:
                stats["expired"] += 1

        return stats


_reservation_manager: Optional[ReservationManager] = None


def get_reservation_manager(
    pending_ttl_seconds: int = 3600, max_reservations: int = 10000
) -> ReservationManager:
    global _reservation_manager
    if _reservation_manager is None:
        _reservation_manager = ReservationManager(
            pending_ttl_seconds, max_reservations
        )
    return _reservation_manager
