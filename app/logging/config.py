"""
Logging configuration - Centralized structlog + stdlib setup.
Call setup_logging() once at app startup.
"""
import os
import sys
import logging
import logging.handlers
import structlog

from app.config.settings import (
    LOG_LEVEL,
    LOG_FORMAT,
    LOG_OUTPUT,
    LOG_FILE_PATH,
    LOG_FILE_MAX_BYTES,
    LOG_FILE_BACKUP_COUNT,
)
from app.logging.context import get_request_id, get_user_id
from app.logging.sanitizer import sanitize_sensitive_data


def _inject_context_vars(logger: any, method_name: str, event_dict: dict) -> dict:
    """Inject ContextVar values (request_id, user_id) into every log entry."""
    request_id = get_request_id()
    if request_id:
        event_dict.setdefault("request_id", request_id)
    user_id = get_user_id()
    if user_id:
        event_dict.setdefault("user_id", user_id)
    return event_dict


def _build_handlers() -> list[logging.Handler]:
    handlers = []

    if LOG_OUTPUT in ("stdout", "both"):
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(LOG_LEVEL)
        handlers.append(stream_handler)

    if LOG_OUTPUT in ("file", "both"):
        log_dir = os.path.dirname(LOG_FILE_PATH)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            filename=LOG_FILE_PATH,
            maxBytes=LOG_FILE_MAX_BYTES,
            backupCount=LOG_FILE_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(LOG_LEVEL)
        handlers.append(file_handler)

    if not handlers:
        handlers.append(logging.StreamHandler(sys.stdout))

    return handlers


def setup_logging() -> None:
    """
    Initialize structlog + stdlib logging. Call once at app startup.

    - Development (LOG_FORMAT=console): colored, human-readable output
    - Production (LOG_FORMAT=json): JSON lines, machine-readable
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        _inject_context_vars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        sanitize_sensitive_data,
    ]

    if LOG_FORMAT == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    # --- Configure structlog ---
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # --- Configure stdlib root logger (uvicorn, sqlalchemy, httpx, etc.) ---
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handlers = _build_handlers()
    for handler in handlers:
        handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    for handler in handlers:
        root_logger.addHandler(handler)
    root_logger.setLevel(LOG_LEVEL)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("authlib").setLevel(logging.WARNING)
