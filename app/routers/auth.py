"""
Auth Router - Authentication endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from jose import JWTError
import os
from app.schemas.auth import (
    LoginRequest, 
    RegisterRequest, 
    TokenResponse, 
    RefreshTokenRequest,
    OAuthURLResponse,
    OAuthCallbackRequest,
    CheckProvidersResponse,
    SignOutRequest,
    UserInfoResponse
)
from app.database.session import get_db
from app.repositories.user_repository import (
    create_user,
    get_user_by_email,
    get_user_by_id
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
    add_token_to_blacklist
)
from app.auth.dependencies import get_current_user
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# Frontend URL for OAuth redirects
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new user with email and password.
    
    Args:
        request: Registration data (email, password, name)
        db: Database session
        
    Returns:
        TokenResponse with access_token, refresh_token, and user info
        
    Raises:
        HTTPException 400: If email already exists
    """
    # Check if user already exists
    existing_user = get_user_by_email(request.email, db)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Hash password
    hashed_pwd = hash_password(request.password)
    
    # Create user data
    user_data = {
        "email": request.email,
        "hashed_password": hashed_pwd,
        "name": request.name,
        "provider": "email",
        "email_verified": False
    }
    
    # Create user in database
    new_user = create_user(user_data, db)
    if not new_user:
        raise HTTPException(status_code=500, detail="Failed to create user")
    
    # Generate tokens
    access_token = create_access_token(str(new_user.id))
    refresh_token = create_refresh_token(str(new_user.id))
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user_id=str(new_user.id),
        email=new_user.email
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Login with email and password.
    
    Args:
        request: Login credentials (email, password)
        db: Database session
        
    Returns:
        TokenResponse with access_token, refresh_token, and user info
        
    Raises:
        HTTPException 401: If credentials are invalid
    """
    # Get user by email
    user = get_user_by_email(request.email, db)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Verify password
    if not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid login method")
    
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Generate tokens
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user_id=str(user.id),
        email=user.email
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Refresh access token using refresh token.
    
    Args:
        request: Refresh token request
        db: Database session
        
    Returns:
        TokenResponse with new access_token and same refresh_token
        
    Raises:
        HTTPException 401: If refresh token is invalid or blacklisted
    """
    try:
        # Verify refresh token
        payload = verify_refresh_token(request.refresh_token)
        user_id = payload.get("sub")
        jti = payload.get("jti")
        
        if not user_id or not jti:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        # Check if refresh token is blacklisted
        if is_token_blacklisted(jti, db):
            raise HTTPException(status_code=401, detail="Token has been revoked")
        
        # Get user from database
        user = get_user_by_id(user_id, db)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Generate new access token
        new_access_token = create_access_token(str(user.id))
        
        return TokenResponse(
            access_token=new_access_token,
            refresh_token=request.refresh_token,  # Return same refresh token
            token_type="bearer",
            user_id=str(user.id),
            email=user.email
        )
        
    except JWTError:
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
        
        # Redirect to frontend with tokens in URL
        callback_url = f"{FRONTEND_URL}/auth/callback?access_token={access_token}&refresh_token={refresh_token}"
        return RedirectResponse(url=callback_url)
        
    except Exception as e:
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
    
    # Return user's registered provider
    return CheckProvidersResponse(providers=[user.provider])


@router.post("/signout")
async def sign_out(
    request: SignOutRequest,
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Sign out user by blacklisting refresh token.
    
    Args:
        request: Sign out request with refresh token
        current_user_id: Current authenticated user ID
        db: Database session
        
    Returns:
        Success message
        
    Raises:
        HTTPException 401: If refresh token is invalid
        HTTPException 500: If blacklist operation fails
    """
    try:
        # Verify and decode refresh token
        payload = verify_refresh_token(request.refresh_token)
        refresh_jti = payload.get("jti")
        refresh_exp_timestamp = payload.get("exp")
        
        if not refresh_jti or not refresh_exp_timestamp:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        # Convert exp timestamp to datetime
        refresh_exp = datetime.fromtimestamp(refresh_exp_timestamp, tz=timezone.utc)
        
        # Add refresh token to blacklist
        success = add_token_to_blacklist(
            token_jti=refresh_jti,
            user_id=current_user_id,
            token_type="refresh",
            expires_at=refresh_exp,
            db=db
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to sign out")
        
        return {"message": "Successfully signed out"}
        
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid refresh token: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to sign out")


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
        provider=user.provider,
        email_verified=user.email_verified,
        created_at=user.created_at.isoformat() if user.created_at else None
    )
