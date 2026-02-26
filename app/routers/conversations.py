"""
Conversations Router - Conversation CRUD endpoints
"""
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.schemas.conversation import (
    ConversationResponse,
    ConversationUpdateRequest,
    ExistsResponse,
    MessageResponse,
)
from app.schemas.presentation import ActivePresentationResponse
from app.auth.dependencies import get_current_user
from app.database.session import get_db
from app.services import conversation_service

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=List[ConversationResponse])
async def list_conversations_endpoint(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all conversations for current user"""
    return conversation_service.list_conversations(user_id, db)


@router.get("/{conversation_id}/exists", response_model=ExistsResponse)
async def check_conversation_exists(
    conversation_id: UUID,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check if conversation exists and belongs to user"""
    exists = conversation_service.check_conversation_exists(str(conversation_id), user_id, db)
    return ExistsResponse(exists=exists)


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: UUID,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get conversation by ID (404 if not found or not owned)"""
    return conversation_service.get_conversation(str(conversation_id), user_id, db)


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation_endpoint(
    conversation_id: UUID,
    body: ConversationUpdateRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update conversation (e.g. title)"""
    return conversation_service.update_conversation(
        str(conversation_id), user_id, body.model_dump(exclude_unset=True), db
    )


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation_endpoint(
    conversation_id: UUID,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a conversation"""
    conversation_service.delete_conversation(str(conversation_id), user_id, db)


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    conversation_id: UUID,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all messages in a conversation"""
    messages = conversation_service.get_messages(str(conversation_id), user_id, db)
    return [
        MessageResponse(
            id=m["id"],
            conversation_id=m["conversation_id"],
            role=m["role"],
            content=m["content"],
            intent=m.get("intent"),
            metadata=m.get("metadata"),
            created_at=m.get("created_at"),
        )
        for m in messages
    ]


@router.get("/{conversation_id}/active-presentation", response_model=ActivePresentationResponse)
async def get_active_presentation_endpoint(
    conversation_id: UUID,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get active presentation ID for a conversation"""
    presentation_id = conversation_service.get_active_presentation(str(conversation_id), user_id, db)
    return ActivePresentationResponse(presentation_id=presentation_id)
