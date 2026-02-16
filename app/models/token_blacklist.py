"""
Token Blacklist Model
"""
from sqlalchemy import Column, String, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database.session import Base
import uuid


class TokenBlacklist(Base):
    """Token Blacklist model for revoked tokens"""
    __tablename__ = "token_blacklist"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token_jti = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_type = Column(String(20), nullable=False)  # 'refresh' only
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    blacklisted_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
