"""
Chat Router - Chat workflow endpoints
TODO: Implement /chat endpoint to execute ChatWorkflow
"""
# from fastapi import APIRouter, Depends
# from app.schemas.chat import ChatRequest, ChatResponse
# from app.auth.dependencies import get_current_user

# router = APIRouter(prefix="/chat", tags=["chat"])

# @router.post("/", response_model=ChatResponse)
# async def chat(
#     request: ChatRequest,
#     current_user_id: str = Depends(get_current_user)
# ):
#     """Process chat message through workflow"""
#     # TODO: Implement chat workflow execution
#     # 1. Set user context
#     # 2. Call ChatWorkflow.run()
#     # 3. Return response
#     pass
