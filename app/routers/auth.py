"""
Auth Router - Authentication endpoints.

Responsibilities:
  - Parse and validate HTTP requests (handled by FastAPI/Pydantic)
  - Delegate business logic to auth_service
  - Build HTTP responses (tokens, cookies, redirects)
"""
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    OAuthURLResponse,
    CheckProvidersResponse,
    UserInfoResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from app.database.session import get_db
from app.auth.oauth import generate_oauth_state, get_google_authorization_url
from app.auth.dependencies import get_current_user
from app.config.settings import COOKIE_SECURE, FRONTEND_URL, REFRESH_TOKEN_EXPIRE_DAYS
from app.logging import get_logger
import app.services.auth_service as auth_service

logger = get_logger(__name__)

REFRESH_TOKEN_COOKIE_KEY = "refresh_token"
REFRESH_TOKEN_MAX_AGE = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600


def _set_refresh_token_cookie(response, refresh_token: str) -> None:
    """Set httpOnly cookie for refresh token."""
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE_KEY,
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=REFRESH_TOKEN_MAX_AGE,
        path="/auth",
    )


def _create_token_response(access_token: str, user_id: str, email: str, refresh_token: str) -> JSONResponse:
    """Create JSONResponse with access_token in body and refresh_token in httpOnly cookie."""
    content = {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user_id,
        "email": email,
    }
    response = JSONResponse(content=content)
    _set_refresh_token_cookie(response, refresh_token)
    return response


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register")
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new user with email and password.
    Returns access_token in JSON, refresh_token in httpOnly cookie.
    """
    result = auth_service.register(request.email, request.password, request.name, db)
    return _create_token_response(
        result["access_token"], result["user_id"], result["email"], result["refresh_token"]
    )


@router.post("/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Login with email and password.
    Returns access_token in JSON, refresh_token in httpOnly cookie.
    """
    result = auth_service.login(request.email, request.password, db)
    return _create_token_response(
        result["access_token"], result["user_id"], result["email"], result["refresh_token"]
    )


@router.post("/refresh")
async def refresh_token(request: Request, db: Session = Depends(get_db)):
    """
    Refresh access token using refresh token from httpOnly cookie.
    Returns only new access_token in JSON (refresh_token stays in cookie).
    """
    refresh_token_value = request.cookies.get(REFRESH_TOKEN_COOKIE_KEY)
    result = auth_service.refresh_access_token(refresh_token_value, db)
    return JSONResponse(content=result)


@router.get("/google", response_model=OAuthURLResponse)
async def google_oauth_url():
    """Get Google OAuth authorization URL."""
    state = generate_oauth_state()
    authorization_url = get_google_authorization_url(state)
    return OAuthURLResponse(authorization_url=authorization_url, state=state)


@router.get("/callback")
async def google_oauth_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="CSRF state token"),
    db: Session = Depends(get_db),
):
    """
    Handle Google OAuth callback and redirect to frontend with tokens.
    On any failure, redirects to frontend login page with an error param.
    """
    try:
        result = await auth_service.handle_google_callback(code, db)
        callback_url = f"{FRONTEND_URL}/auth/callback?access_token={result['access_token']}"
        response = RedirectResponse(url=callback_url)
        _set_refresh_token_cookie(response, result["refresh_token"])
        return response
    except Exception as e:
        error_code = str(e) if str(e) else "unexpected_error"
        logger.warning("oauth_callback_failed", provider="google", error_message=str(e))
        return RedirectResponse(url=f"{FRONTEND_URL}/login?error={error_code}")


@router.get("/check-providers", response_model=CheckProvidersResponse)
async def check_providers(
    email: str = Query(..., description="User email to check"),
    db: Session = Depends(get_db),
):
    """Check which authentication providers are available for an email."""
    providers = auth_service.check_providers(email, db)
    return CheckProvidersResponse(providers=providers)


@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Request password reset. Sends reset link to email if user exists with email provider.
    Always returns 200 to avoid email enumeration.
    """
    await auth_service.request_password_reset(request.email, db)
    return {"message": "If an account exists with that email, you will receive a reset link."}


@router.get("/verify-reset-token")
async def verify_reset_token(token: str = Query(...), db: Session = Depends(get_db)):
    """Verify if reset token is valid (for frontend to check before showing form)."""
    auth_service.verify_password_reset_token(token, db)
    return {"valid": True}


@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset password using token from email link."""
    auth_service.reset_password(request.token, request.new_password, db)
    return {"message": "Password reset successful. Please login with your new password."}


@router.post("/signout")
async def sign_out(request: Request, db: Session = Depends(get_db)):
    """Sign out user by blacklisting refresh token from cookie and clearing cookie."""
    refresh_token_value = request.cookies.get(REFRESH_TOKEN_COOKIE_KEY)
    auth_service.signout(refresh_token_value, db)

    response = JSONResponse(content={"message": "Successfully signed out"})
    response.delete_cookie(key=REFRESH_TOKEN_COOKIE_KEY, path="/auth")
    return response


@router.get("/me", response_model=UserInfoResponse)
async def get_current_user_info(
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current authenticated user information."""
    user_data = auth_service.get_user_info(current_user_id, db)
    return UserInfoResponse(**user_data)
