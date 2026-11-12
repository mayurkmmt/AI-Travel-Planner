from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from app.models.chat import MessageRole


class ChatMessageIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    trip_id: Optional[int] = None


class ChatMessageOut(BaseModel):
    id: int
    trip_id: int
    role: MessageRole
    content: str
    message_type: str
    created_at: datetime
    model_config = {"from_attributes": True}


class ChatResponse(BaseModel):
    message: ChatMessageOut
    agent_reply: ChatMessageOut
    trip_id: int
    slot_state: dict
    status: str
