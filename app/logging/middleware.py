"""
Request logging middleware - Assigns request_id and logs request lifecycle.
"""
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.logging.context import set_request_id, clear_request_id, clear_user_id

logger = structlog.get_logger("middleware.request")

# Paths that generate too much noise (health checks, docs)
_SKIP_LOG_PATHS = frozenset({"/health", "/docs", "/openapi.json", "/favicon.ico"})


class RequestLoggingMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _SKIP_LOG_PATHS:
            return await call_next(request)

        # 1. Generate and store request_id
        request_id = uuid.uuid4().hex[:12]
        set_request_id(request_id)

        # 2. Bind request context for all downstream log calls
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        # 3. Log request started
        logger.info("request_started")

        start_time = time.perf_counter()
        status_code = 500  # default in case of unhandled exception

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            logger.exception("request_failed")
            raise
        finally:
            duration_ms = round((time.perf_counter() - start_time) * 1000)

            # 4. Log request completed
            logger.info(
                "request_completed",
                status_code=status_code,
                duration_ms=duration_ms,
            )

            # Cleanup context
            structlog.contextvars.clear_contextvars()
            clear_request_id()
            clear_user_id()
