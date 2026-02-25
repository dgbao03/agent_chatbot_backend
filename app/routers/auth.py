"""
Auth Router - Authentication endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from jose import JWTError
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
from app.repositories.user_repository import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    update_user,
)
from app.auth.utils import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_refresh_token
)
from app.auth.oauth import (
    generate_oauth_state,
    get_google_authorization_url,
    exchange_google_code_for_token,
    get_google_user_info,
    get_or_create_oauth_user
)
from app.repositories.token_blacklist_repository import (
    is_token_blacklisted,
    add_token_to_blacklist,
)
from app.repositories.password_reset_token_repository import (
    create_token as create_reset_token,
    get_valid_token,
    mark_token_used,
)
from app.services.email_service import send_password_reset_email
from app.auth.dependencies import get_current_user
from app.config.settings import COOKIE_SECURE, FRONTEND_URL, REFRESH_TOKEN_EXPIRE_DAYS
from app.logging import get_logger
from datetime import datetime, timezone

logger = get_logger(__name__)

# Cookie settings for refresh token (httpOnly)
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
    """Create JSONResponse with access_token in body and refresh_token in cookie."""
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
    existing_user = get_user_by_email(request.email, db)
    if existing_user:
        logger.warning("register_failed", email=request.email, reason="email_already_registered")
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pwd = hash_password(request.password)
    user_data = {
        "email": request.email,
        "hashed_password": hashed_pwd,
        "name": request.name,
        "providers": ["email"],
        "email_verified": False
    }

    new_user = create_user(user_data, db)
    if not new_user:
        raise HTTPException(status_code=500, detail="Failed to create user")

    access_token = create_access_token(str(new_user.id))
    refresh_token = create_refresh_token(str(new_user.id))

    logger.info("user_registered", email=request.email, auth_method="email")

    return _create_token_response(access_token, str(new_user.id), new_user.email, refresh_token)


@router.post("/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Login with email and password.
    Returns access_token in JSON, refresh_token in httpOnly cookie.
    """
    user = get_user_by_email(request.email, db)
    if not user:
        logger.warning("login_failed", email=request.email, reason="user_not_found")
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.hashed_password:
        logger.warning("login_failed", email=request.email, reason="no_password_provider")
        raise HTTPException(status_code=401, detail="Invalid login method")

    if not verify_password(request.password, user.hashed_password):
        logger.warning("login_failed", email=request.email, reason="wrong_password")
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    logger.info("login_success", email=request.email, auth_method="password")

    return _create_token_response(access_token, str(user.id), user.email, refresh_token)


@router.post("/refresh")
async def refresh_token(request: Request, db: Session = Depends(get_db)):
    """
    Refresh access token using refresh token from httpOnly cookie.
    Returns only new access_token in JSON (refresh_token stays in cookie).
    """
    refresh_token_value = request.cookies.get(REFRESH_TOKEN_COOKIE_KEY)
    if not refresh_token_value:
        logger.warning("token_refresh_failed", reason="no_refresh_token_cookie")
        raise HTTPException(status_code=401, detail="Refresh token not found")

    try:
        payload = verify_refresh_token(refresh_token_value)
        user_id = payload.get("sub")
        jti = payload.get("jti")

        if not user_id or not jti:
            logger.warning("token_refresh_failed", reason="invalid_payload")
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        if is_token_blacklisted(jti, db):
            logger.warning("token_refresh_failed", reason="token_blacklisted")
            raise HTTPException(status_code=401, detail="Token has been revoked")

        user = get_user_by_id(user_id, db)
        if not user:
            logger.warning("token_refresh_failed", reason="user_not_found")
            raise HTTPException(status_code=401, detail="User not found")

        new_access_token = create_access_token(str(user.id))

        logger.info("token_refreshed")

        return JSONResponse(content={
            "access_token": new_access_token,
            "token_type": "bearer",
            "user_id": str(user.id),
            "email": user.email,
        })

    except JWTError:
        logger.warning("token_refresh_failed", reason="jwt_error")
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@router.get("/google", response_model=OAuthURLResponse)
async def google_oauth_url():
    """
    Get Google OAuth authorization URL.
    
    Returns:
        OAuthURLResponse with authorization URL and state token
    """
    state = generate_oauth_state()
    authorization_url = get_google_authorization_url(state)
    
    return OAuthURLResponse(
        authorization_url=authorization_url,
        state=state
    )


@router.get("/callback")
async def google_oauth_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="CSRF state token"),
    db: Session = Depends(get_db)
):
    """
    Handle Google OAuth callback and redirect to frontend with tokens.
    
    Args:
        code: Authorization code from Google
        state: CSRF state token
        db: Database session
        
    Returns:
        RedirectResponse to frontend with tokens in URL params
        
    Raises:
        HTTPException 400: If code exchange fails
        HTTPException 500: If user info retrieval fails
    """
    try:
        # Exchange code for token
        token_data = await exchange_google_code_for_token(code)
        if not token_data:
            # Redirect to frontend with error
            error_url = f"{FRONTEND_URL}/login?error=oauth_failed"
            return RedirectResponse(url=error_url)
        
        # Get user info from Google
        google_access_token = token_data.get("access_token")
        user_info = await get_google_user_info(google_access_token)
        if not user_info:
            error_url = f"{FRONTEND_URL}/login?error=user_info_failed"
            return RedirectResponse(url=error_url)
        
        # Extract user data
        email = user_info.get("email")
        provider_user_id = user_info.get("id")
        name = user_info.get("name")
        avatar_url = user_info.get("picture")
        
        if not email or not provider_user_id:
            error_url = f"{FRONTEND_URL}/login?error=missing_user_data"
            return RedirectResponse(url=error_url)
        
        # Get or create user
        user, is_new = get_or_create_oauth_user(
            email=email,
            provider="google",
            provider_user_id=provider_user_id,
            name=name,
            avatar_url=avatar_url,
            db=db
        )
        
        if not user:
            error_url = f"{FRONTEND_URL}/login?error=user_creation_failed"
            return RedirectResponse(url=error_url)
        
        # Generate JWT tokens
        access_token = create_access_token(str(user.id))
        refresh_token = create_refresh_token(str(user.id))

        logger.info("oauth_callback_success", provider="google", email=email, is_new_user=is_new)

        # Redirect to frontend with access_token in URL, refresh_token in httpOnly cookie
        callback_url = f"{FRONTEND_URL}/auth/callback?access_token={access_token}"
        response = RedirectResponse(url=callback_url)
        _set_refresh_token_cookie(response, refresh_token)
        return response
        
    except Exception as e:
        logger.warning("oauth_callback_failed", provider="google", error_message=str(e))
        # Redirect to frontend with error
        error_url = f"{FRONTEND_URL}/login?error=unexpected_error"
        return RedirectResponse(url=error_url)


@router.get("/check-providers", response_model=CheckProvidersResponse)
async def check_providers(
    email: str = Query(..., description="User email to check"),
    db: Session = Depends(get_db)
):
    """
    Check which authentication providers are available for an email.
    
    Args:
        email: User email to check
        db: Database session
        
    Returns:
        CheckProvidersResponse with list of available providers
    """
    user = get_user_by_email(email, db)
    
    if not user:
        # Email not registered, all providers available
        return CheckProvidersResponse(providers=["email", "google"])
    
    # Return user's registered providers
    return CheckProvidersResponse(providers=user.providers or [])


@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Request password reset. Sends reset link to email if user exists with email provider.
    Always returns 200 to avoid email enumeration.
    """
    user = get_user_by_email(request.email, db)
    if not user:
        return {"message": "If an account exists with that email, you will receive a reset link."}

    if "email" not in (user.providers or []):
        return {"message": "If an account exists with that email, you will receive a reset link."}

    token_str = create_reset_token(str(user.id), expires_minutes=15, db=db)
    if not token_str:
        return {"message": "If an account exists with that email, you will receive a reset link."}

    reset_link = f"{FRONTEND_URL}/reset-password?token={token_str}"
    sent = await send_password_reset_email(user.email, reset_link)

    logger.info("password_reset_requested", email=request.email)

    return {"message": "If an account exists with that email, you will receive a reset link."}


@router.get("/verify-reset-token")
async def verify_reset_token(token: str = Query(...), db: Session = Depends(get_db)):
    """
    Verify if reset token is valid (for frontend to check before showing form).
    """
    token_record = get_valid_token(token, db)
    if not token_record:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link.")
    return {"valid": True}


@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    Reset password using token from email link.
    """
    token_record = get_valid_token(request.token, db)
    if not token_record:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link. Please request a new one.")

    hashed_pwd = hash_password(request.new_password)
    updated = update_user(str(token_record.user_id), {"hashed_password": hashed_pwd}, db)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update password.")

    mark_token_used(request.token, db)

    logger.info("password_reset_completed", user_id=str(token_record.user_id))

    return {"message": "Password reset successful. Please login with your new password."}


@router.post("/signout")
async def sign_out(request: Request, db: Session = Depends(get_db)):
    """
    Sign out user by blacklisting refresh token from cookie and clearing cookie.
    """
    logger.info("signout")

    response = JSONResponse(content={"message": "Successfully signed out"})
    response.delete_cookie(key=REFRESH_TOKEN_COOKIE_KEY, path="/auth")

    refresh_token_value = request.cookies.get(REFRESH_TOKEN_COOKIE_KEY)
    if refresh_token_value:
        try:
            payload = verify_refresh_token(refresh_token_value)
            refresh_jti = payload.get("jti")
            refresh_exp_timestamp = payload.get("exp")
            user_id = payload.get("sub")

            if refresh_jti and refresh_exp_timestamp and user_id:
                refresh_exp = datetime.fromtimestamp(refresh_exp_timestamp, tz=timezone.utc)
                add_token_to_blacklist(
                    token_jti=refresh_jti,
                    user_id=user_id,
                    token_type="refresh",
                    expires_at=refresh_exp,
                    db=db
                )
        except (JWTError, Exception):
            pass  # Cookie cleared anyway, blacklist is best-effort

    return response


@router.get("/me", response_model=UserInfoResponse)
async def get_current_user_info(
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current authenticated user information.
    
    Args:
        current_user_id: Current authenticated user ID from JWT
        db: Database session
        
    Returns:
        UserInfoResponse with user details
        
    Raises:
        HTTPException 401: If user not found
    """
    # Get user from database
    user = get_user_by_id(current_user_id, db)
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return UserInfoResponse(
        user_id=str(user.id),
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
        providers=user.providers or [],
        email_verified=user.email_verified,
        created_at=user.created_at.isoformat() if user.created_at else None
    )
