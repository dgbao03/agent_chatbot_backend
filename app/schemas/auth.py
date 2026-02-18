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


class OAuthURLResponse(BaseModel):
    """Response model for OAuth authorization URL"""
    authorization_url: str = Field(..., description="Google OAuth authorization URL")
    state: str = Field(..., description="CSRF state token")


class OAuthCallbackRequest(BaseModel):
    """Request model for OAuth callback"""
    code: str = Field(..., description="Authorization code from OAuth provider")
    state: Optional[str] = Field(None, description="CSRF state token")


class CheckProvidersResponse(BaseModel):
    """Response model for checking user auth providers"""
    providers: list[str] = Field(..., description="List of auth providers (email, google)")


class SignOutRequest(BaseModel):
    """Request model for sign out"""
    refresh_token: str = Field(..., description="JWT refresh token to revoke")


class ForgotPasswordRequest(BaseModel):
    """Request model for forgot password"""
    email: EmailStr = Field(..., description="User's email address")


class ResetPasswordRequest(BaseModel):
    """Request model for reset password (with token from email link)"""
    token: str = Field(..., description="Password reset token from email link")
    new_password: str = Field(..., min_length=6, description="New password (min 6 characters)")


class UserInfoResponse(BaseModel):
    """Response model for current user information"""
    user_id: str = Field(..., description="User's ID")
    email: str = Field(..., description="User's email")
    name: Optional[str] = Field(None, description="User's display name")
    avatar_url: Optional[str] = Field(None, description="User's avatar URL")
    providers: list[str] = Field(..., description="List of auth providers (email, google)")
    email_verified: bool = Field(..., description="Whether email is verified")
    created_at: Optional[str] = Field(None, description="Account creation timestamp")
