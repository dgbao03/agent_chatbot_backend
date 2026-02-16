"""
Auth Schemas - Pydantic models for authentication endpoints
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class RegisterRequest(BaseModel):
    """Request model for user registration"""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=6, description="User's password (min 6 characters)")
    name: Optional[str] = Field(None, description="User's display name")


class LoginRequest(BaseModel):
    """Request model for user login"""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")


class TokenResponse(BaseModel):
    """Response model for authentication tokens"""
    access_token: str = Field(..., description="JWT access token (30 minutes)")
    refresh_token: str = Field(..., description="JWT refresh token (7 days)")
    token_type: str = Field(default="bearer", description="Token type")
    user_id: str = Field(..., description="User's ID")
    email: str = Field(..., description="User's email")


class RefreshTokenRequest(BaseModel):
    """Request model for refreshing access token"""
    refresh_token: str = Field(..., description="JWT refresh token")
