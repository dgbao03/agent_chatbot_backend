"""
Authentication middleware for WorkflowServer.
Verifies JWT tokens from Supabase and stores user_id in context.
"""
import json
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.datastructures import Headers
from config.supabase_client import get_supabase_client
from config.workflow_context import set_current_user_id


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to verify JWT tokens and inject user_id into request body.
    This ensures user_id is verified from JWT and cannot be spoofed by frontend.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Skip auth for health check, OPTIONS, and static UI routes
        if request.url.path == "/health" or \
           request.method == "OPTIONS" or \
           not request.url.path.startswith("/workflows/"):
            return await call_next(request)
        
        # Get Authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"error": "Missing or invalid Authorization header"}
            )
        
        # Extract token
        token = auth_header.replace("Bearer ", "")
        
        try:
            # Verify token with Supabase
            supabase = get_supabase_client()
            user_response = supabase.auth.get_user(token)
            
            if not user_response or not user_response.user:
                return JSONResponse(
                    status_code=401,
                    content={"error": "Invalid or expired token"}
                )
            
            # Extract user_id from verified JWT
            user_id = user_response.user.id
            
            print(f"\n=== AUTH MIDDLEWARE ===")
            print(f"✅ JWT verified - user_id: {user_id}")
            print(f"=======================\n")
            
            # Store user_id in context var for workflow to access
            set_current_user_id(user_id)
            
            # Also attach to request state
            request.state.user_id = user_id
            request.state.user = user_response.user
            
            # Continue to next middleware/route handler
            response = await call_next(request)
            return response
            
        except Exception as e:
            print(f"Auth middleware error: {e}")
            return JSONResponse(
                status_code=401,
                content={"error": f"Authentication failed: {str(e)}"}
            )
