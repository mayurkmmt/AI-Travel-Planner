from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from app.database import SessionLocal, get_db
from app.models.user import User
from app.models.trip import Trip, TripStatus
from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.core.dependencies import get_current_user
from app.schemas.chat import ChatMessageIn, ChatResponse, ChatMessageOut
from app.services import chat_service
from app.limiter import limiter

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _generate_plan_in_web_process(trip_id: int) -> None:
    """Fallback for local development when Redis/Celery is unavailable."""
    db = SessionLocal()
    try:
        from app.services.generation_service import generate_plan_sync
        generate_plan_sync(trip_id, db)
    finally:
        db.close()


@router.post("/", response_model=ChatResponse)
@limiter.limit("20/minute")
def send_message(
    request: Request,
    payload: ChatMessageIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.trip_id:
        trip = db.query(Trip).filter(Trip.id == payload.trip_id, Trip.user_id == current_user.id).first()
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found")
    else:
        trip = Trip(user_id=current_user.id, status=TripStatus.DRAFT)
        db.add(trip)
        db.commit()
        db.refresh(trip)

    session = chat_service.get_or_create_session(trip, db)
    chat_service.reset_invalid_draft(trip, session, db)

    user_msg = ChatMessage(trip_id=trip.id, role=MessageRole.USER, content=payload.message)
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    reply_text, new_status = chat_service.process_message(
        user_message=payload.message,
        db=db,
        trip=trip,
        session=session,
        background_tasks=background_tasks,
    )

    agent_msg = ChatMessage(
        trip_id=trip.id,
        role=MessageRole.ASSISTANT,
        content=reply_text,
        message_type="status" if new_status in ("creating", "generating") else "text",
    )
    db.add(agent_msg)
    db.commit()
    db.refresh(agent_msg)

    return ChatResponse(
        message=ChatMessageOut.model_validate(user_msg),
        agent_reply=ChatMessageOut.model_validate(agent_msg),
        trip_id=trip.id,
        slot_state=session.slot_state or {},
        status=new_status,
    )


@router.get("/{trip_id}/history/")
def get_chat_history(
    trip_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trip = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == current_user.id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.trip_id == trip_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "trip_id": trip_id,
        "trip_status": trip.status.value,
        "messages": [ChatMessageOut.model_validate(m) for m in reversed(messages)],
        "slot_state": (trip.chat_session.slot_state if trip.chat_session else {}),
    }
