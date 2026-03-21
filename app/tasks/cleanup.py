"""
Token Cleanup Scheduler - Integrated into FastAPI server lifecycle.

Runs cleanup every 24 hours automatically when the server is running.
No external cron or fixed paths needed.
"""
import time
from apscheduler.schedulers.background import BackgroundScheduler

from app.database.session import SessionLocal
from app.repositories.token_blacklist_repository import TokenBlacklistRepository
from app.repositories.password_reset_token_repository import PasswordResetTokenRepository
from app.logging import get_logger

logger = get_logger(__name__)

CLEANUP_INTERVAL_HOURS = 24

scheduler = BackgroundScheduler()


def run_cleanup() -> None:
    """Run cleanup for token_blacklist and password_reset_tokens."""
    logger.info("cleanup_started")
    start = time.perf_counter()
    db = SessionLocal()
    try:
        TokenBlacklistRepository(db).cleanup_expired_tokens()
        PasswordResetTokenRepository(db).cleanup_expired_reset_tokens()
        duration_ms = round((time.perf_counter() - start) * 1000)
        logger.info("cleanup_completed", duration_ms=duration_ms)
    except Exception as e:
        duration_ms = round((time.perf_counter() - start) * 1000)
        logger.error("cleanup_failed", error_type=type(e).__name__, error_message=str(e), duration_ms=duration_ms)
    finally:
        db.close()


def start_scheduler() -> None:
    """Start the background cleanup scheduler."""
    scheduler.add_job(
        run_cleanup,
        trigger="interval",
        hours=CLEANUP_INTERVAL_HOURS,
        id="token_cleanup",
        replace_existing=True,
    )
    scheduler.start()


def stop_scheduler() -> None:
    """Shutdown the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
