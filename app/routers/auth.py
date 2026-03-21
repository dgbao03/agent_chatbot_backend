"""
Auth Router - Authentication endpoints.

Responsibilities:
  - Parse and validate HTTP requests (handled by FastAPI/Pydantic)
  - Delegate business logic to auth_service
  - Build HTTP responses (tokens, cookies, redirects)
"""
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse, JSONResponse

from app.types.http.auth import (
    LoginRequest,
    RegisterRequest,
    TokenBodyResponse,
    RefreshTokenResponse,
    MessageResponse,
    TokenValidResponse,
    OAuthURLResponse,
    CheckProvidersResponse,
    UserInfoResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from app.auth.oauth import generate_oauth_state, get_google_authorization_url
from app.auth.dependencies import get_current_user
from app.config.settings import COOKIE_SECURE, FRONTEND_URL, REFRESH_TOKEN_EXPIRE_DAYS
from app.services.auth_service import AuthService
from app.dependencies.services import get_auth_service
from app.logging import get_logger

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


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=TokenBodyResponse)
async def register(
    request: RegisterRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    """
    Register a new user with email and password.
    Returns access_token in JSON, refresh_token in httpOnly cookie.
    """
    result = service.register(request.email, request.password, request.name)
    _set_refresh_token_cookie(response, result["refresh_token"])
    return TokenBodyResponse(
        access_token=result["access_token"],
        token_type="bearer",
        user_id=result["user_id"],
        email=result["email"],
    )


@router.post("/login", response_model=TokenBodyResponse)
async def login(
    request: LoginRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    """
    Login with email and password.
    Returns access_token in JSON, refresh_token in httpOnly cookie.
    """
    result = service.login(request.email, request.password)
    _set_refresh_token_cookie(response, result["refresh_token"])
    return TokenBodyResponse(
        access_token=result["access_token"],
        token_type="bearer",
        user_id=result["user_id"],
        email=result["email"],
    )


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    """
    Refresh access token using refresh token from httpOnly cookie.
    Returns only new access_token in JSON (refresh_token stays in cookie).
    """
    refresh_token_value = request.cookies.get(REFRESH_TOKEN_COOKIE_KEY)
    return service.refresh_access_token(refresh_token_value)


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
    service: AuthService = Depends(get_auth_service),
):
    """
    Handle Google OAuth callback and redirect to frontend with tokens.
    On any failure, redirects to frontend login page with an error param.
    """
    try:
        result = await service.handle_google_callback(code)
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
    service: AuthService = Depends(get_auth_service),
):
    """Check which authentication providers are available for an email."""
    providers = service.check_providers(email)
    return CheckProvidersResponse(providers=providers)


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    request: ForgotPasswordRequest,
    service: AuthService = Depends(get_auth_service),
):
    """
    Request password reset. Sends reset link to email if user exists with email provider.
    Always returns 200 to avoid email enumeration.
    """
    await service.request_password_reset(request.email)
    return MessageResponse(message="If an account exists with that email, you will receive a reset link.")


@router.get("/verify-reset-token", response_model=TokenValidResponse)
async def verify_reset_token(
    token: str = Query(...),
    service: AuthService = Depends(get_auth_service),
):
    """Verify if reset token is valid (for frontend to check before showing form)."""
    service.verify_password_reset_token(token)
    return TokenValidResponse(valid=True)


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    request: ResetPasswordRequest,
    service: AuthService = Depends(get_auth_service),
):
    """Reset password using token from email link."""
    service.reset_password(request.token, request.new_password)
    return MessageResponse(message="Password reset successful. Please login with your new password.")


@router.post("/signout")
async def sign_out(
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    """Sign out user by blacklisting refresh token from cookie and clearing cookie."""
    refresh_token_value = request.cookies.get(REFRESH_TOKEN_COOKIE_KEY)
    service.signout(refresh_token_value)

    response = JSONResponse(content={"message": "Successfully signed out"})
    response.delete_cookie(key=REFRESH_TOKEN_COOKIE_KEY, path="/auth")
    return response


@router.get("/me", response_model=UserInfoResponse)
async def get_current_user_info(
    current_user_id: str = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
):
    """Get current authenticated user information."""
    user_data = service.get_user_info(current_user_id)
    return UserInfoResponse(**user_data)
