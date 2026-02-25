"""
Centralized application settings — single source of truth for all config values.
All values are read from environment variables with sensible defaults.
"""
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# LLM
# ============================================================
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_SECURITY_MODEL: str = os.getenv("LLM_SECURITY_MODEL", "gpt-4o-mini")
LLM_SUMMARY_MODEL: str = os.getenv("LLM_SUMMARY_MODEL", "gpt-4o-mini")
LLM_TIMEOUT: float = float(os.getenv("LLM_TIMEOUT", "300"))
LLM_SECURITY_TIMEOUT: float = float(os.getenv("LLM_SECURITY_TIMEOUT", "30"))
LLM_SUMMARY_TIMEOUT: float = float(os.getenv("LLM_SUMMARY_TIMEOUT", "120"))

# ============================================================
# Database
# ============================================================
DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")

# ============================================================
# JWT
# ============================================================
ACCESS_TOKEN_SECRET_KEY: Optional[str] = os.getenv("ACCESS_TOKEN_SECRET_KEY")
REFRESH_TOKEN_SECRET_KEY: Optional[str] = os.getenv("REFRESH_TOKEN_SECRET_KEY")
ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# ============================================================
# Google OAuth
# ============================================================
GOOGLE_CLIENT_ID: Optional[str] = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET: Optional[str] = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:4040/auth/callback")

# ============================================================
# Frontend
# ============================================================
FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5174")

# ============================================================
# CORS
# ============================================================
CORS_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:5174").split(",")
    if origin.strip()
]

# ============================================================
# Cookie
# ============================================================
COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"

# ============================================================
# SMTP
# ============================================================
SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER: Optional[str] = os.getenv("SMTP_USER")
SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")
SMTP_FROM_EMAIL: Optional[str] = os.getenv("SMTP_FROM_EMAIL") or SMTP_USER
SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "Chat Assistant")
# Port 465 = SSL/TLS from start (use_tls=True). Port 587 = STARTTLS (use_tls=False, auto-upgrade)
SMTP_USE_TLS: bool = SMTP_PORT == 465

# ============================================================
# Logging
# ============================================================
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT: str = os.getenv("LOG_FORMAT", "console")   # "console" | "json"
LOG_OUTPUT: str = os.getenv("LOG_OUTPUT", "stdout")    # "stdout" | "file" | "both"
LOG_FILE_PATH: str = os.getenv("LOG_FILE_PATH", "logs/app.log")
LOG_FILE_MAX_BYTES: int = int(os.getenv("LOG_FILE_MAX_BYTES", str(50 * 1024 * 1024)))  # 50MB
LOG_FILE_BACKUP_COUNT: int = int(os.getenv("LOG_FILE_BACKUP_COUNT", "10"))
