"""
Auth Router - Authentication endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from jose import JWTError
from app.schemas.auth import (
    LoginRequest, 
    RegisterRequest, 
    TokenResponse, 
    RefreshTokenRequest,
    OAuthURLResponse,
    OAuthCallbackRequest,
    CheckProvidersResponse
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
        HTTPException 401: If refresh token is invalid
    """
    try:
        # Verify refresh token
        user_id = verify_refresh_token(request.refresh_token)
        
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
    Handle Google OAuth callback.
    
    Args:
        code: Authorization code from Google
        state: CSRF state token
        db: Database session
        
    Returns:
        TokenResponse with access_token, refresh_token, and user info
        
    Raises:
        HTTPException 400: If code exchange fails
        HTTPException 500: If user info retrieval fails
    """
    # Exchange code for token
    token_data = await exchange_google_code_for_token(code)
    if not token_data:
        raise HTTPException(status_code=400, detail="Failed to exchange authorization code")
    
    # Get user info from Google
    access_token = token_data.get("access_token")
    user_info = await get_google_user_info(access_token)
    if not user_info:
        raise HTTPException(status_code=500, detail="Failed to get user information")
    
    # Extract user data
    email = user_info.get("email")
    provider_user_id = user_info.get("id")
    name = user_info.get("name")
    avatar_url = user_info.get("picture")
    
    if not email or not provider_user_id:
        raise HTTPException(status_code=400, detail="Missing required user information")
    
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
        raise HTTPException(status_code=500, detail="Failed to create or update user")
    
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
