import logging

from fastapi import APIRouter, HTTPException

from api.reservation_manager import get_reservation_manager
from api.reservation_models import (ReservationStatusEnum,
                                    ReservationStatusResponse)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reservations", tags=["Reservations"])

reservation_manager = get_reservation_manager()


@router.get(
    "/{reservation_id}/status",
    response_model=ReservationStatusResponse,
    summary="Check reservation status",
    description="Check current status of reservation by ID"
)
async def check_reservation_status(reservation_id: str):
    reservation = await reservation_manager.get_reservation(reservation_id)

    if not reservation:
        raise HTTPException(
            status_code=404,
            detail=f"Reservation {reservation_id} not found"
        )

    status_messages = {
        ReservationStatusEnum.PENDING_APPROVAL: (
            "Your reservation is being reviewed by our administrator. "
            "You will be notified once a decision is made."
        ),
        ReservationStatusEnum.APPROVED: (
            "Great news! Your reservation has been approved. "
            "You will receive confirmation details shortly."
        ),
        ReservationStatusEnum.REJECTED: (
            "Unfortunately, your reservation was not approved. "
            "Please contact us or try a different time."
        ),
        ReservationStatusEnum.EXPIRED: (
            "Your reservation request has expired. "
            "Please submit a new reservation request."
        ),
    }

    return ReservationStatusResponse(
        reservation_id=reservation.reservation_id,
        status=reservation.status,
        message=status_messages.get(
            reservation.status,
            "Reservation status unknown"
        ),
        admin_comment=reservation.admin_comment
    )


@router.get(
    "/conversation/{conversation_id}",
    response_model=ReservationStatusResponse,
    summary="Get reservation by conversation",
    description="Get most recent reservation for a conversation"
)
async def get_reservation_by_conversation(conversation_id: str):
    reservation = await reservation_manager.get_reservation_by_conversation(
        conversation_id
    )

    if not reservation:
        raise HTTPException(
            status_code=404,
            detail=f"No reservation found for conversation {conversation_id}"
        )

    status_messages = {
        ReservationStatusEnum.PENDING_APPROVAL: (
            "Your reservation is being reviewed by our administrator. "
            "You will be notified once a decision is made."
        ),
        ReservationStatusEnum.APPROVED: (
            "Great news! Your reservation has been approved. "
            "You will receive confirmation details shortly."
        ),
        ReservationStatusEnum.REJECTED: (
            "Unfortunately, your reservation was not approved. "
            "Please contact us or try a different time."
        ),
        ReservationStatusEnum.EXPIRED: (
            "Your reservation request has expired. "
            "Please submit a new reservation request."
        ),
    }

    return ReservationStatusResponse(
        reservation_id=reservation.reservation_id,
        status=reservation.status,
        message=status_messages.get(
            reservation.status,
            "Reservation status unknown"
        ),
        admin_comment=reservation.admin_comment
    )
