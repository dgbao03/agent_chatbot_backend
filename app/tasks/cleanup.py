"""
Token Cleanup Script - Run via cron for periodic cleanup of expired/revoked tokens.

Usage:
    python -m app.tasks.cleanup

Cron example (2am daily):
    0 2 * * * cd /path/to/agent_chat_backend && ./venv/bin/python -m app.tasks.cleanup
"""
from dotenv import load_dotenv

load_dotenv()

from app.database.session import SessionLocal
from app.repositories.token_blacklist_repository import cleanup_expired_tokens
from app.repositories.password_reset_token_repository import cleanup_expired_reset_tokens


def run_cleanup() -> None:
    """Run cleanup for token_blacklist and password_reset_tokens."""
    db = SessionLocal()
    try:
        blacklist_deleted = cleanup_expired_tokens(db)
        reset_tokens_deleted = cleanup_expired_reset_tokens(db)
        print(f"Cleanup done: blacklist={blacklist_deleted}, reset_tokens={reset_tokens_deleted}")
    finally:
        db.close()


if __name__ == "__main__":
    run_cleanup()
