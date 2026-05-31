import asyncio
import logging
import uuid
from collections import OrderedDict
from datetime import datetime
from typing import Dict, List, Optional

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
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

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


class ReservationManager:
    """
    Manages reservations in memory with TTL for pending approvals.
    
    Features:
    - In-memory storage (OrderedDict for efficient access)
    - Automatic expiration for pending reservations
    - Thread-safe with asyncio.Lock
    - Admin approval/rejection workflow
    """

    def __init__(
        self,
        pending_ttl_seconds: int = 3600,
        max_reservations: int = 10000
    ):
        self.reservations: OrderedDict[str, Reservation] = OrderedDict()
        self.pending_ttl_seconds = pending_ttl_seconds
        self.max_reservations = max_reservations
        self.lock = asyncio.Lock()
        logger.info(
            f"ReservationManager initialized "
            f"(Pending TTL: {pending_ttl_seconds}s, Max: {max_reservations})"
        )

    async def create_reservation(
        self, data: ReservationCreate
    ) -> ReservationResponse:
        async with self.lock:
            return self._create_reservation_internal(data)

    def create_reservation_sync(self, data: ReservationCreate) -> ReservationResponse:
        return self._create_reservation_internal(data)

    def _create_reservation_internal(self, data: ReservationCreate) -> ReservationResponse:
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
            f"Created reservation {reservation_id} for {data.name} {data.surname}"
        )
        return reservation.to_response()

    async def get_reservation(
        self, reservation_id: str
    ) -> Optional[ReservationResponse]:
        async with self.lock:
            reservation = self.reservations.get(reservation_id)
            if not reservation:
                return None

            if reservation.is_expired(self.pending_ttl_seconds):
                logger.info(
                    f"Reservation {reservation_id} expired, marking as EXPIRED"
                )
                reservation.status = ReservationStatusEnum.EXPIRED
                reservation.updated_at = datetime.now()

            return reservation.to_response()

    async def get_pending_reservations(self) -> List[ReservationResponse]:
        async with self.lock:
            await self._cleanup_expired()
            pending = [
                res.to_response()
                for res in self.reservations.values()
                if res.status == ReservationStatusEnum.PENDING_APPROVAL
            ]
            return pending

    async def get_all_reservations(self) -> List[ReservationResponse]:
        async with self.lock:
            await self._cleanup_expired()
            return [res.to_response() for res in self.reservations.values()]

    async def approve_reservation(
        self, reservation_id: str, comment: Optional[str] = None
    ) -> Optional[ReservationResponse]:
        async with self.lock:
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
            return reservation.to_response()

    async def reject_reservation(
        self, reservation_id: str, comment: Optional[str] = None
    ) -> Optional[ReservationResponse]:
        async with self.lock:
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
            return reservation.to_response()

    async def get_reservation_by_conversation(
        self, conversation_id: str
    ) -> Optional[ReservationResponse]:
        async with self.lock:
            for res in reversed(self.reservations.values()):
                if res.conversation_id == conversation_id:
                    if res.is_expired(self.pending_ttl_seconds):
                        res.status = ReservationStatusEnum.EXPIRED
                        res.updated_at = datetime.now()
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

    async def cleanup_task(self) -> None:
        logger.info("Starting reservation cleanup task")
        while True:
            try:
                await asyncio.sleep(300)
                async with self.lock:
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
