"""
Token Cleanup Scheduler - Integrated into FastAPI server lifecycle.

Runs cleanup every 24 hours automatically when the server is running.
No external cron or fixed paths needed.
"""
from apscheduler.schedulers.background import BackgroundScheduler

from app.database.session import SessionLocal
from app.repositories.token_blacklist_repository import cleanup_expired_tokens
from app.repositories.password_reset_token_repository import cleanup_expired_reset_tokens

CLEANUP_INTERVAL_HOURS = 24

scheduler = BackgroundScheduler()


def run_cleanup() -> None:
    """Run cleanup for token_blacklist and password_reset_tokens."""
    db = SessionLocal()
    try:
        cleanup_expired_tokens(db)
        cleanup_expired_reset_tokens(db)
    except Exception:
        pass
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
