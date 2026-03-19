"""
Workflow Schemas - Pydantic models for workflow endpoints
"""
from pydantic import BaseModel
from typing import Optional
from uuid import UUID


class StartEventPayload(BaseModel):
    """Payload for workflow start event - matches FE format."""
    user_input: str
    conversation_id: Optional[UUID] = None


class WorkflowRunRequest(BaseModel):
    """Request body for POST /workflows/chat/run."""
    start_event: StartEventPayload
