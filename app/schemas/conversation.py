"""
Conversation Schemas - Pydantic models for conversation endpoints
"""
from pydantic import BaseModel
from typing import Optional, List, Any


class ConversationResponse(BaseModel):
    id: str
    user_id: str
    title: Optional[str] = None
    active_presentation_id: Optional[str] = None
    next_presentation_id_counter: int = 1
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ConversationUpdateRequest(BaseModel):
    title: Optional[str] = None


class ExistsResponse(BaseModel):
    exists: bool


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    intent: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True
