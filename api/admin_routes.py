import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.auth import verify_admin_api_key
from api.chatbot_adapter import ChatbotAdapter
from api.reservation_manager import get_reservation_manager
from api.reservation_models import (ReservationApproval,
                                    ReservationListResponse,
                                    ReservationResponse, ReservationStatusEnum)
from graphs.state import ReservationData
from mcp_client import get_mcp_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Admin"])

reservation_manager = get_reservation_manager()
mcp_client = get_mcp_client()


@router.get(
    "/reservations/pending",
    response_model=list[ReservationResponse],
    summary="Get all pending reservations",
    description="Retrieve list of all reservations awaiting admin approval",
    dependencies=[Depends(verify_admin_api_key)]
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
    description="Retrieve all reservations with optional status filter",
    dependencies=[Depends(verify_admin_api_key)]
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
    description="Retrieve detailed information about specific reservation",
    dependencies=[Depends(verify_admin_api_key)]
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
    description="Approve pending reservation and resume LangGraph workflow",
    dependencies=[Depends(verify_admin_api_key)]
)
async def approve_reservation(
    reservation_id: str,
    approval: ReservationApproval
):
    """
    Approve reservation using Admin Agent with LangChain LCEL chain
    This endpoint resumes the LangGraph workflow
    The graph continues to MCP persistence node
    """
    if not approval.approved:
        raise HTTPException(
            status_code=400,
            detail="Use reject endpoint to reject reservation"
        )

    try:
        reservation = await reservation_manager.get_reservation(reservation_id)

        if not reservation:
            raise HTTPException(
                status_code=404,
                detail=f"Reservation {reservation_id} not found"
            )

        if reservation.status != ReservationStatusEnum.PENDING_APPROVAL:
            raise HTTPException(
                status_code=400,
                detail=f"Reservation is not pending approval (status: {reservation.status})"
            )

        conversation_id = reservation.conversation_id

        logger.info(
            f"Approving reservation {reservation_id} via graph resume "
            f"(conversation: {conversation_id})"
        )

        adapter = ChatbotAdapter()
        chatbot = adapter.get_instance()

        config = {"configurable": {"thread_id": conversation_id}}

        reservation_data = ReservationData(
            name=reservation.name,
            surname=reservation.surname,
            car_plate=reservation.car_plate,
            start_time=reservation.start_time,
            end_time=reservation.end_time
        )

        chatbot.graph.update_state(config, {
            "admin_decision": "approved",
            "admin_comment": approval.comment or "Approved by administrator",
            "reservation_data": reservation_data,
            "reservation_id": reservation_id
        }, as_node="wait_for_admin_decision")

        logger.info(
            f"Updated graph state with approval for {reservation_id}. "
            f"Resuming graph from interrupt..."
        )

        result = None
        async for chunk in chatbot.graph.astream(None, config, stream_mode="values"):
            result = chunk
            logger.debug(f"Graph chunk: {chunk.get('reservation_status')}")

        logger.info(
            f"Graph resumed and completed for {reservation_id}. "
            f"MCP persisted: {result.get('mcp_persisted', False)}"
        )

        reservation = await reservation_manager.approve_reservation(
            reservation_id,
            approval.comment or "Approved by administrator"
        )

        if not reservation:
            raise HTTPException(
                status_code=404,
                detail=f"Reservation {reservation_id} not found after approval"
            )

        logger.info(
            f"Reservation {reservation_id} approved and graph workflow completed"
        )

        return reservation

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error approving reservation {reservation_id}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to approve reservation: {str(e)}"
        )


@router.post(
    "/reservations/{reservation_id}/reject",
    response_model=ReservationResponse,
    summary="Reject reservation",
    description="Reject pending reservation and resume LangGraph workflow",
    dependencies=[Depends(verify_admin_api_key)]
)
async def reject_reservation(
    reservation_id: str,
    approval: ReservationApproval
):
    """
    Reject reservation using Admin Agent with LangChain LCEL chain
    This endpoint resumes the LangGraph workflow
    The graph continues to rejection processing (skips MCP)
    """
    if approval.approved:
        raise HTTPException(
            status_code=400,
            detail="Use approve endpoint to approve reservation"
        )

    if not approval.comment:
        raise HTTPException(
            status_code=400,
            detail="Comment is required when rejecting a reservation"
        )

    try:
        reservation = await reservation_manager.get_reservation(reservation_id)

        if not reservation:
            raise HTTPException(
                status_code=404,
                detail=f"Reservation {reservation_id} not found"
            )

        if reservation.status != ReservationStatusEnum.PENDING_APPROVAL:
            raise HTTPException(
                status_code=400,
                detail=f"Reservation is not pending approval (status: {reservation.status})"
            )

        conversation_id = reservation.conversation_id

        logger.info(
            f"Rejecting reservation {reservation_id} via graph resume "
            f"(conversation: {conversation_id})"
        )

        adapter = ChatbotAdapter()
        chatbot = adapter.get_instance()

        config = {"configurable": {"thread_id": conversation_id}}

        reservation_data = ReservationData(
            name=reservation.name,
            surname=reservation.surname,
            car_plate=reservation.car_plate,
            start_time=reservation.start_time,
            end_time=reservation.end_time
        )

        chatbot.graph.update_state(config, {
            "admin_decision": "rejected",
            "admin_comment": approval.comment,
            "reservation_data": reservation_data,
            "reservation_id": reservation_id
        }, as_node="wait_for_admin_decision")

        logger.info(
            f"Updated graph state with rejection for {reservation_id}. "
            f"Resuming graph from interrupt..."
        )

        async for chunk in chatbot.graph.astream(None, config, stream_mode="values"):
            result = chunk
            logger.debug(f"Graph chunk: {chunk.get('reservation_status')}")

        logger.info(
            f"Graph resumed and completed for {reservation_id}. "
            f"Rejection processed."
        )

        reservation = await reservation_manager.reject_reservation(
            reservation_id,
            approval.comment
        )

        if not reservation:
            raise HTTPException(
                status_code=404,
                detail=f"Reservation {reservation_id} not found after rejection"
            )

        logger.info(
            f"Reservation {reservation_id} rejected and graph workflow completed"
        )

        return reservation

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error rejecting reservation {reservation_id}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reject reservation: {str(e)}"
        )


@router.get(
    "/stats",
    summary="Get reservation statistics",
    description="Get overall statistics about reservations",
    dependencies=[Depends(verify_admin_api_key)]
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
