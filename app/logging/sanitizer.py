"""
Log sanitizer - Processor to mask sensitive data before log output.
Runs as part of structlog processor pipeline.
"""
import re
from typing import Any

SENSITIVE_FIELDS = frozenset({
    "password",
    "hashed_password",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "secret",
    "secret_key",
    "authorization",
    "cookie",
    "openai_api_key",
    "tavily_api_key",
    "weather_api_key",
    "finnhub_api_key",
    "google_client_secret",
    "supabase_anon_key",
    "supabase_service_key",
})

_EMAIL_PATTERN = re.compile(r"^([^@]{1})[^@]*([^@]{1})@(.+)$")


def mask_email(email: str) -> str:
    match = _EMAIL_PATTERN.match(email)
    if not match:
        return "***@***"
    first, last, domain = match.groups()
    return f"{first}***{last}@{domain}"


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return normalized in SENSITIVE_FIELDS


def _sanitize_value(key: str, value: Any) -> Any:
    if _is_sensitive_key(key):
        return "***REDACTED***"

    if isinstance(value, str) and key.lower() == "email":
        return mask_email(value)

    if isinstance(value, dict):
        return {k: _sanitize_value(k, v) for k, v in value.items()}

    return value


def sanitize_sensitive_data(logger: Any, method_name: str, event_dict: dict) -> dict:
    """structlog processor: mask sensitive fields in log events."""
    return {k: _sanitize_value(k, v) for k, v in event_dict.items()}
