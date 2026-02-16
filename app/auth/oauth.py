"""
OAuth Utils - Google OAuth flow implementation
"""
import secrets
import os
from typing import Dict, Optional, Tuple
from authlib.integrations.starlette_client import OAuth
from sqlalchemy.orm import Session
from app.repositories.user_repository import get_user_by_email, create_user
from app.models import User

# Google OAuth configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:4040/auth/callback")

# Initialize OAuth client
oauth = OAuth()
oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)


def generate_oauth_state() -> str:
    """
    Generate CSRF state token for OAuth flow.
    
    Returns:
        Random state string
    """
    return secrets.token_urlsafe(32)


def get_google_authorization_url(state: str) -> str:
    """
    Generate Google OAuth authorization URL.
    
    Args:
        state: CSRF state token
        
    Returns:
        Authorization URL string
    """
    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account"
    }
    
    # Build query string
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    return f"{base_url}?{query_string}"


async def exchange_google_code_for_token(code: str) -> Optional[Dict]:
    """
    Exchange authorization code for access token.
    
    Args:
        code: Authorization code from Google
        
    Returns:
        Token dict with access_token, id_token, etc., or None if failed
    """
    import httpx
    
    token_url = "https://oauth2.googleapis.com/token"
    
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(token_url, data=data)
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
    except Exception:
        return None


async def get_google_user_info(access_token: str) -> Optional[Dict]:
    """
    Get user information from Google using access token.
    
    Args:
        access_token: Google access token
        
    Returns:
        User info dict with email, name, picture, etc., or None if failed
    """
    import httpx
    
    userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
    except Exception:
        return None


def get_or_create_oauth_user(
    email: str,
    provider: str,
    provider_user_id: str,
    name: Optional[str],
    avatar_url: Optional[str],
    db: Session
) -> Tuple[Optional[User], bool]:
    """
    Get existing OAuth user or create new one.
    
    Args:
        email: User's email
        provider: OAuth provider (e.g., 'google')
        provider_user_id: User ID from OAuth provider
        name: User's name
        avatar_url: User's avatar URL
        db: Database session
        
    Returns:
        Tuple of (User object or None, is_new_user boolean)
    """
    try:
        # Check if user exists with this email
        existing_user = get_user_by_email(email, db)
        
        if existing_user:
            # User exists - update OAuth info if needed
            if existing_user.provider != provider or existing_user.provider_user_id != provider_user_id:
                existing_user.provider = provider
                existing_user.provider_user_id = provider_user_id
                
                # Update profile info if not set
                if not existing_user.name and name:
                    existing_user.name = name
                if not existing_user.avatar_url and avatar_url:
                    existing_user.avatar_url = avatar_url
                
                existing_user.email_verified = True
                db.commit()
                db.refresh(existing_user)
            
            return (existing_user, False)
        else:
            # Create new user
            user_data = {
                "email": email,
                "provider": provider,
                "provider_user_id": provider_user_id,
                "name": name,
                "avatar_url": avatar_url,
                "email_verified": True,
                "hashed_password": None  # OAuth users don't have password
            }
            
            new_user = create_user(user_data, db)
            return (new_user, True)
            
    except Exception:
        db.rollback()
        return (None, False)
