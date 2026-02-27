"""
FastAPI Application Entry Point
"""
import traceback
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from app.logging import setup_logging, get_logger
from app.logging.middleware import RequestLoggingMiddleware
from app.config.settings import CORS_ORIGINS
from app.routers import auth, conversations, presentations, workflow
from app.tasks.cleanup import start_scheduler, stop_scheduler
from app.exceptions import AppException

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("app_started", version="2.0.0", port=4040)
    start_scheduler()
    yield
    stop_scheduler()
    logger.info("app_stopped")


app = FastAPI(
    title="Agent Chat API",
    description="AI Chat application with presentation generation",
    version="2.0.0",
    lifespan=lifespan,
)

# Middleware (order matters: last added = first executed)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# AppException handler — converts service-layer exceptions to HTTP responses
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


# Global exception handler
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(
        "unhandled_error",
        error_type=type(exc).__name__,
        error_message=str(exc),
        stack_trace=traceback.format_exc(),
        method=request.method,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# Register routers
app.include_router(auth.router)
app.include_router(conversations.router, prefix="/api")
app.include_router(presentations.router, prefix="/api")
app.include_router(workflow.router)  # /workflows/chat/run - no /api prefix (FE calls directly)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "version": "2.0.0"}

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Agent Chat API",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=4040,
        reload=False
    )
