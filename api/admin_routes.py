import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.reservation_manager import get_reservation_manager
from api.reservation_models import (ReservationApproval,
                                    ReservationListResponse,
                                    ReservationResponse, ReservationStatusEnum)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Admin"])

reservation_manager = get_reservation_manager()


@router.get(
    "/reservations/pending",
    response_model=list[ReservationResponse],
    summary="Get all pending reservations",
    description="Retrieve list of all reservations awaiting admin approval"
)
async def get_pending_reservations():
    try:
        pending = await reservation_manager.get_pending_reservations()
        logger.info(f"Retrieved {len(pending)} pending reservations")
        return pending
    except Exception as e:
        logger.error(f"Error retrieving pending reservations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/reservations",
    response_model=ReservationListResponse,
    summary="Get all reservations",
    description="Retrieve all reservations with optional status filter"
)
async def get_all_reservations(
    status: Optional[ReservationStatusEnum] = Query(
        None, description="Filter by status"
    )
):
    try:
        all_reservations = await reservation_manager.get_all_reservations()

        if status:
            filtered = [r for r in all_reservations if r.status == status]
        else:
            filtered = all_reservations

        stats = reservation_manager.get_stats()

        return ReservationListResponse(
            reservations=filtered,
            total=stats["total"],
            pending=stats["pending"],
            approved=stats["approved"],
            rejected=stats["rejected"]
        )
    except Exception as e:
        logger.error(f"Error retrieving reservations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/reservations/{reservation_id}",
    response_model=ReservationResponse,
    summary="Get reservation details",
    description="Retrieve detailed information about specific reservation"
)
async def get_reservation(reservation_id: str):
    reservation = await reservation_manager.get_reservation(reservation_id)

    if not reservation:
        raise HTTPException(
            status_code=404,
            detail=f"Reservation {reservation_id} not found"
        )

    return reservation


@router.post(
    "/reservations/{reservation_id}/approve",
    response_model=ReservationResponse,
    summary="Approve reservation",
    description="Approve pending reservation and notify user"
)
async def approve_reservation(
    reservation_id: str,
    approval: ReservationApproval
):
    """Approve reservation"""
    if not approval.approved:
        raise HTTPException(
            status_code=400,
            detail="Use reject endpoint to reject reservation"
        )

    reservation = await reservation_manager.approve_reservation(
        reservation_id, approval.comment
    )

    if not reservation:
        raise HTTPException(
            status_code=404,
            detail=f"Reservation {reservation_id} not found or not pending"
        )

    logger.info(
        f"Reservation {reservation_id} approved by admin "
        f"(comment: {approval.comment})"
    )
    return reservation


@router.post(
    "/reservations/{reservation_id}/reject",
    response_model=ReservationResponse,
    summary="Reject reservation",
    description="Reject pending reservation and notify user with reason"
)
async def reject_reservation(
    reservation_id: str,
    approval: ReservationApproval
):
    if approval.approved:
        raise HTTPException(
            status_code=400,
            detail="Use approve endpoint to approve reservation"
        )

    reservation = await reservation_manager.reject_reservation(
        reservation_id, approval.comment
    )

    if not reservation:
        raise HTTPException(
            status_code=404,
            detail=f"Reservation {reservation_id} not found or not pending"
        )

    logger.info(
        f"Reservation {reservation_id} rejected by admin "
        f"(comment: {approval.comment})"
    )
    return reservation


@router.get(
    "/stats",
    summary="Get reservation statistics",
    description="Get overall statistics about reservations"
)
async def get_reservation_stats():
    """Get reservation statistics"""
    stats = reservation_manager.get_stats()
    return {
        "total_reservations": stats["total"],
        "pending_approval": stats["pending"],
        "approved": stats["approved"],
        "rejected": stats["rejected"],
        "expired": stats["expired"]
    }
