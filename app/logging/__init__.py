"""
Logging module - Structured logging for Agent Chat Backend.
"""
import structlog

from app.logging.config import setup_logging

__all__ = ["setup_logging", "get_logger"]


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a named structured logger.

    Usage:
        from app.logging import get_logger
        logger = get_logger(__name__)
        logger.info("event_name", key="value")
    """
    return structlog.get_logger(name)
