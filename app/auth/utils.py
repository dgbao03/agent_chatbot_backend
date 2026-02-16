"""
Auth Utils - JWT and password utilities
TODO: Implement JWT creation/verification and password hashing
"""
# from passlib.context import CryptContext
# from jose import jwt, JWTError
# from datetime import datetime, timedelta
# import os

# # Password hashing context
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# # JWT settings
# ACCESS_TOKEN_SECRET_KEY = os.getenv("ACCESS_TOKEN_SECRET_KEY")
# REFRESH_TOKEN_SECRET_KEY = os.getenv("REFRESH_TOKEN_SECRET_KEY")
# ALGORITHM = os.getenv("ALGORITHM", "HS256")
# ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
# REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))


# def hash_password(password: str) -> str:
#     """Hash a plain text password"""
#     return pwd_context.hash(password)


# def verify_password(plain_password: str, hashed_password: str) -> bool:
#     """Verify a password against a hash"""
#     return pwd_context.verify(plain_password, hashed_password)


# def create_access_token(user_id: str) -> str:
#     """Create a JWT access token"""
#     expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
#     payload = {
#         "sub": user_id,
#         "type": "access",
#         "exp": expire
#     }
#     return jwt.encode(payload, ACCESS_TOKEN_SECRET_KEY, algorithm=ALGORITHM)


# def create_refresh_token(user_id: str) -> str:
#     """Create a JWT refresh token"""
#     expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
#     payload = {
#         "sub": user_id,
#         "type": "refresh",
#         "exp": expire
#     }
#     return jwt.encode(payload, REFRESH_TOKEN_SECRET_KEY, algorithm=ALGORITHM)


# def verify_access_token(token: str) -> str:
#     """
#     Verify access token and return user_id
#     
#     Args:
#         token: JWT access token
#     
#     Returns:
#         user_id: User ID from token
#     
#     Raises:
#         JWTError: If token is invalid
#     """
#     try:
#         payload = jwt.decode(token, ACCESS_TOKEN_SECRET_KEY, algorithms=[ALGORITHM])
#         user_id = payload.get("sub")
#         token_type = payload.get("type")
#         
#         if token_type != "access":
#             raise JWTError("Invalid token type")
#         
#         return user_id
#     except JWTError as e:
#         raise JWTError(f"Token verification failed: {str(e)}")


# def verify_refresh_token(token: str) -> str:
#     """
#     Verify refresh token and return user_id
#     
#     Args:
#         token: JWT refresh token
#     
#     Returns:
#         user_id: User ID from token
#     
#     Raises:
#         JWTError: If token is invalid
#     """
#     try:
#         payload = jwt.decode(token, REFRESH_TOKEN_SECRET_KEY, algorithms=[ALGORITHM])
#         user_id = payload.get("sub")
#         token_type = payload.get("type")
#         
#         if token_type != "refresh":
#             raise JWTError("Invalid token type")
#         
#         return user_id
#     except JWTError as e:
#         raise JWTError(f"Token verification failed: {str(e)}")
