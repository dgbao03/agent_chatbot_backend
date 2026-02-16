"""
UserFacts Router - User facts CRUD endpoints
TODO: Implement user facts management endpoints
"""
# from fastapi import APIRouter, Depends
# from typing import List
# from app.schemas.user_fact import UserFactResponse, DeleteUserFactRequest
# from app.auth.dependencies import get_current_user

# router = APIRouter(prefix="/user-facts", tags=["user-facts"])

# @router.get("/", response_model=List[UserFactResponse])
# async def list_user_facts(current_user_id: str = Depends(get_current_user)):
#     """Get all user facts for current user"""
#     # TODO: Implement list user facts
#     pass

# @router.delete("/{key}")
# async def delete_user_fact(
#     key: str,
#     current_user_id: str = Depends(get_current_user)
# ):
#     """Delete a user fact by key"""
#     # TODO: Implement delete user fact
#     pass
