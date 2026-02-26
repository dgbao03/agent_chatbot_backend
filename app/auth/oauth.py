"""
OAuth Utils - Google OAuth flow implementation
"""
import secrets
from typing import Dict, Optional, Tuple
from authlib.integrations.starlette_client import OAuth
from sqlalchemy.orm import Session
from app.repositories.user_repository import get_user_by_email, create_user, update_user
from app.models import User
from app.config.settings import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI
from app.logging import get_logger

logger = get_logger(__name__)

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
        logger.exception("exchange_google_code_failed")
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
        logger.exception("get_google_user_info_failed")
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
            # User exists - add OAuth provider to providers list (don't overwrite)
            current_providers = list(existing_user.providers or [])
            if provider not in current_providers:
                current_providers.append(provider)

            update_data: Dict = {
                "providers": current_providers,
                "provider_user_id": provider_user_id,
                "email_verified": True,
            }
            if not existing_user.name and name:
                update_data["name"] = name
            if not existing_user.avatar_url and avatar_url:
                update_data["avatar_url"] = avatar_url

            updated = update_user(str(existing_user.id), update_data, db)
            return (updated, False)
        else:
            # Create new user
            user_data = {
                "email": email,
                "providers": [provider],
                "provider_user_id": provider_user_id,
                "name": name,
                "avatar_url": avatar_url,
                "email_verified": True,
                "hashed_password": None  # OAuth users don't have password
            }
            
            new_user = create_user(user_data, db)
            return (new_user, True)
            
    except Exception:
        logger.exception("get_or_create_oauth_user_failed")
        db.rollback()
        return (None, False)
