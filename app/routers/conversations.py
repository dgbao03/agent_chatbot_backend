"""
Conversations Router - Conversation CRUD endpoints
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
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
from app.repositories.conversation_repository import (
    list_conversations,
    get_conversation_by_id,
    update_conversation,
    delete_conversation,
)
from app.repositories.chat_repository import load_all_messages_for_conversation
from app.repositories.presentation_repository import get_active_presentation

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=List[ConversationResponse])
async def list_conversations_endpoint(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all conversations for current user"""
    data = list_conversations(user_id, db)
    return data


@router.get("/{conversation_id}/exists", response_model=ExistsResponse)
async def check_conversation_exists(
    conversation_id: UUID,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check if conversation exists and belongs to user"""
    conv = get_conversation_by_id(str(conversation_id), user_id, db)
    return ExistsResponse(exists=conv is not None)


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: UUID,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get conversation by ID (404 if not found or not owned)"""
    conv = get_conversation_by_id(str(conversation_id), user_id, db)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation_endpoint(
    conversation_id: UUID,
    body: ConversationUpdateRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update conversation (e.g. title)"""
    conv = update_conversation(str(conversation_id), user_id, body.model_dump(exclude_unset=True), db)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation_endpoint(
    conversation_id: UUID,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a conversation"""
    deleted = delete_conversation(str(conversation_id), user_id, db)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    conversation_id: UUID,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all messages in a conversation"""
    messages = load_all_messages_for_conversation(str(conversation_id), user_id, db)
    # Map to MessageResponse - include metadata for PPTX (pages, slide_id, etc.)
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
    presentation_id = get_active_presentation(str(conversation_id), db, user_id=user_id)
    return ActivePresentationResponse(presentation_id=presentation_id)
