"""
Email Service - Send emails via SMTP (forgot password, etc.)
"""
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import aiosmtplib
from app.config.settings import (
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    SMTP_FROM_EMAIL,
    SMTP_FROM_NAME,
    SMTP_USE_TLS,
)
from app.logging import get_logger

logger = get_logger(__name__)


def _is_smtp_configured() -> bool:
    """Check if SMTP is properly configured."""
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


async def send_password_reset_email(to_email: str, reset_link: str) -> bool:
    """
    Send password reset email.

    Args:
        to_email: Recipient email address
        reset_link: Full URL to reset password page (e.g. https://app.com/reset-password?token=xxx)

    Returns:
        True if sent successfully, False otherwise
    """
    if not _is_smtp_configured():
        return False

    subject = "Reset your password - Chat Assistant"
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2>Reset your password</h2>
        <p>You requested a password reset. Click the link below to set a new password:</p>
        <p><a href="{reset_link}" style="color: #2563eb; text-decoration: underline;">Reset Password</a></p>
        <p>This link will expire in 15 minutes.</p>
        <p>If you didn't request this, you can safely ignore this email.</p>
        <hr style="margin-top: 24px; border: none; border-top: 1px solid #e5e7eb;">
        <p style="font-size: 12px; color: #6b7280;">Chat Assistant</p>
    </body>
    </html>
    """
    plain_body = f"""Reset your password\n\nClick the link below to set a new password:\n{reset_link}\n\nThis link will expire in 15 minutes.\n\nIf you didn't request this, you can safely ignore this email."""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
    msg["To"] = to_email
    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USER,
            password=SMTP_PASSWORD,
            use_tls=SMTP_USE_TLS,  # True for port 465, False for 587 (STARTTLS auto)
        )
        return True
    except Exception:
        logger.exception("send_password_reset_email_failed")
        return False
