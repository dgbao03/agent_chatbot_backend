"""
Workflow Router - Manual API endpoint for Chat Workflow.
Replaces WorkflowServer with direct FastAPI integration.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.auth.dependencies import get_current_user
from app.auth.context import (
    set_current_user_id,
    clear_current_user_id,
    set_current_db_session,
    clear_current_db_session,
)
from app.exceptions import AppException
from app.config.prompts import ERROR_GENERAL
from app.database.session import get_db
from app.workflows.workflow import ChatWorkflow
from app.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/workflows", tags=["workflows"])


class StartEventPayload(BaseModel):
    """Request body for workflow start event - matches FE format."""
    user_input: str
    conversation_id: Optional[str] = None


class WorkflowRunRequest(BaseModel):
    """Request body for POST /workflows/chat/run."""
    start_event: StartEventPayload


@router.post("/chat/run")
async def run_chat_workflow(
    body: WorkflowRunRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Run the Chat Workflow manually.
    Sets auth context (user_id, db) before execution.
    Returns format expected by frontend: { status, result } or { error }.
    """
    if not body.start_event.user_input or not body.start_event.user_input.strip():
        return JSONResponse(
            status_code=422,
            content={"status": "error", "error": "user_input is required and cannot be empty"},
        )

    # Set context for workflow (replaces AuthMiddleware)
    set_current_user_id(user_id)
    set_current_db_session(db)

    try:
        workflow = ChatWorkflow()
        handler = workflow.run(
            user_input=body.start_event.user_input,
            conversation_id=body.start_event.conversation_id,
        )
        result = await handler

        # FE expects: { status: 'completed', result: { value: { result: ... } } }
        return {
            "status": "completed",
            "result": {
                "value": {
                    "result": result,
                }
            },
        }
    except AppException as e:
        logger.warning("workflow_error", error_type=type(e).__name__, detail=e.message)
        return JSONResponse(
            status_code=e.status_code,
            content={"status": "error", "error": e.message},
        )
    except Exception as e:
        logger.error("workflow_unexpected_error", error_type=type(e).__name__, detail=str(e))
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": ERROR_GENERAL},
        )
    finally:
        clear_current_user_id()
        clear_current_db_session()
