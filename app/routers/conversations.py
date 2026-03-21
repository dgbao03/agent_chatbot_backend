"""
Conversations Router - Conversation CRUD endpoints
"""
from uuid import UUID
from fastapi import APIRouter, Depends
from typing import List

from app.types.http.conversation import (
    ConversationResponse,
    ConversationUpdateRequest,
    ExistsResponse,
    MessageResponse,
)
from app.types.http.presentation import ActivePresentationResponse
from app.auth.dependencies import get_current_user
from app.services.conversation_service import ConversationService
from app.dependencies.services import get_conversation_service

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=List[ConversationResponse])
async def list_conversations_endpoint(
    user_id: str = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
):
    """Get all conversations for current user"""
    return service.list_conversations(user_id)


@router.get("/{conversation_id}/exists", response_model=ExistsResponse)
async def check_conversation_exists(
    conversation_id: UUID,
    user_id: str = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
):
    """Check if conversation exists and belongs to user"""
    exists = service.check_conversation_exists(str(conversation_id), user_id)
    return ExistsResponse(exists=exists)


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: UUID,
    user_id: str = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
):
    """Get conversation by ID (404 if not found or not owned)"""
    return service.get_conversation(str(conversation_id), user_id)


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation_endpoint(
    conversation_id: UUID,
    body: ConversationUpdateRequest,
    user_id: str = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
):
    """Update conversation (e.g. title)"""
    return service.update_conversation(
        str(conversation_id), user_id, body.model_dump(exclude_unset=True)
    )


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation_endpoint(
    conversation_id: UUID,
    user_id: str = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
):
    """Delete a conversation"""
    service.delete_conversation(str(conversation_id), user_id)


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    conversation_id: UUID,
    user_id: str = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
):
    """Get all messages in a conversation"""
    messages = service.get_messages(str(conversation_id), user_id)
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
    service: ConversationService = Depends(get_conversation_service),
):
    """Get active presentation ID for a conversation"""
    presentation_id = service.get_active_presentation(str(conversation_id), user_id)
    return ActivePresentationResponse(presentation_id=presentation_id)
