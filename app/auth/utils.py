"""
Auth Utils - JWT and password utilities
"""
import bcrypt
from jose import jwt, JWTError
from datetime import datetime, timedelta
import os
import uuid
from dotenv import load_dotenv
from app.logging import get_logger

load_dotenv()

logger = get_logger(__name__)

# JWT settings
ACCESS_TOKEN_SECRET_KEY = os.getenv("ACCESS_TOKEN_SECRET_KEY")
REFRESH_TOKEN_SECRET_KEY = os.getenv("REFRESH_TOKEN_SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))


def hash_password(password: str) -> str:
    """
    Hash a plain text password using bcrypt.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password string
    """
    # Generate salt and hash password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password from database
        
    Returns:
        True if password matches, False otherwise
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except Exception:
        logger.exception("verify_password_failed")
        return False


def create_access_token(user_id: str) -> str:
    """
    Create a JWT access token.
    
    Args:
        user_id: User ID to encode in token
        
    Returns:
        JWT access token string
    """
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    jti = str(uuid.uuid4())  # Generate unique JWT ID
    
    payload = {
        "sub": user_id,
        "type": "access",
        "exp": expire,
        "jti": jti
    }
    return jwt.encode(payload, ACCESS_TOKEN_SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """
    Create a JWT refresh token.
    
    Args:
        user_id: User ID to encode in token
        
    Returns:
        JWT refresh token string
    """
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    jti = str(uuid.uuid4())  # Generate unique JWT ID
    
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": expire,
        "jti": jti
    }
    return jwt.encode(payload, REFRESH_TOKEN_SECRET_KEY, algorithm=ALGORITHM)


def verify_access_token(token: str) -> dict:
    """
    Verify access token and return payload.
    
    Args:
        token: JWT access token
    
    Returns:
        payload: Token payload containing sub, jti, exp, type
    
    Raises:
        JWTError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, ACCESS_TOKEN_SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        token_type = payload.get("type")
        
        if not user_id:
            raise JWTError("Token missing user ID")
        
        if token_type != "access":
            raise JWTError("Invalid token type")
        
        return payload
    except JWTError as e:
        raise JWTError(f"Token verification failed: {str(e)}")


def verify_refresh_token(token: str) -> dict:
    """
    Verify refresh token and return payload.
    
    Args:
        token: JWT refresh token
    
    Returns:
        payload: Token payload containing sub, jti, exp, type
    
    Raises:
        JWTError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, REFRESH_TOKEN_SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        token_type = payload.get("type")
        
        if not user_id:
            raise JWTError("Token missing user ID")
        
        if token_type != "refresh":
            raise JWTError("Invalid token type")
        
        return payload
    except JWTError as e:
        raise JWTError(f"Token verification failed: {str(e)}")
