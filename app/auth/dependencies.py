"""
Auth Dependencies - FastAPI dependency functions for authentication
"""
import structlog
from fastapi import Depends, HTTPException, Header
from typing import Optional
from jose import JWTError
from app.auth.utils import verify_access_token
from app.logging import get_logger
from app.logging.context import set_user_id

logger = get_logger(__name__)


async def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    """
    FastAPI dependency to extract and verify user_id from JWT token.
    
    Usage:
        @router.get("/protected")
        async def protected_route(user_id: str = Depends(get_current_user)):
            return {"user_id": user_id}
    
    Args:
        authorization: Authorization header with Bearer token
    
    Returns:
        user_id (str): Verified user ID from JWT token
    
    Raises:
        HTTPException 401: If token is missing or invalid
    """
    if not authorization or not authorization.startswith("Bearer "):
        logger.warning("auth_failed", reason="missing_or_invalid_header")
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header"
        )
    
    token = authorization.replace("Bearer ", "")
    
    try:
        payload = verify_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            logger.warning("auth_failed", reason="invalid_token_payload")
            raise HTTPException(status_code=401, detail="Invalid token")

        structlog.contextvars.bind_contextvars(user_id=user_id)
        set_user_id(user_id)
        return user_id
    except JWTError as e:
        logger.warning("auth_failed", reason="jwt_error", error_message=str(e))
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("auth_failed", reason="unexpected_error", error_message=str(e))
        raise HTTPException(status_code=401, detail="Authentication failed")
