"""
User Model - SQLAlchemy ORM
Maps to 'users' table for authentication
"""
from sqlalchemy import Column, String, Boolean, text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP, ARRAY
from sqlalchemy.orm import relationship
from app.database.session import Base


class User(Base):
    __tablename__ = "users"
    
    # Primary Key
    id = Column(UUID, primary_key=True, server_default=text("gen_random_uuid()"))
    
    # Authentication
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=True)  # Nullable for OAuth users
    
    # Profile
    name = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    
    # OAuth - providers: list of auth methods (email, google, etc.)
    providers = Column(ARRAY(String), nullable=False, server_default=text("ARRAY['email']"))
    provider_user_id = Column(String(255), nullable=True)
    
    # Email verification
    email_verified = Column(Boolean, nullable=False, server_default="false")
    
    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    
    # Relationships
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    user_facts = relationship("UserFact", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, providers={self.providers})>"
