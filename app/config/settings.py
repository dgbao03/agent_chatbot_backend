"""
Centralized application settings — single source of truth for all config values.
All values are read from environment variables with sensible defaults.
"""
import os
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
