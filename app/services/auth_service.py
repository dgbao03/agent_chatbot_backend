"""
Auth Service - Business logic for all authentication use cases.

Centralizes auth business logic, keeping routers thin.
Each method receives plain parameters and raises AppException subclasses
on failure; callers (routers / global handler) convert these to HTTP responses.
"""
from typing import Optional
from datetime import datetime, timezone

from jose import JWTError

from app.repositories.user_repository import UserRepository
from app.repositories.token_blacklist_repository import TokenBlacklistRepository
from app.repositories.password_reset_token_repository import PasswordResetTokenRepository
from app.services.email_service import EmailService
from app.auth.utils import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
)
from app.auth.oauth import (
    exchange_google_code_for_token,
    get_google_user_info,
    get_or_create_oauth_user,
)
from app.config import settings
from app.config.settings import FRONTEND_URL
from app.exceptions import (
    AppException,
    AuthenticationError,
    DatabaseError,
    ValidationError,
)
from app.logging import get_logger

logger = get_logger(__name__)


class AuthService:

    def __init__(
        self,
        user_repo: UserRepository,
        token_blacklist_repo: TokenBlacklistRepository,
        password_reset_repo: PasswordResetTokenRepository,
        email_service: EmailService,
    ):
        self.user_repo = user_repo
        self.token_blacklist_repo = token_blacklist_repo
        self.password_reset_repo = password_reset_repo
        self.email_service = email_service

    def register(self, email: str, password: str, name: Optional[str]) -> dict:
        """
        Register a new user with email/password.

        Returns:
            dict with access_token, refresh_token, user_id, email
        Raises:
            AppException (400): email already registered
            DatabaseError (500): user creation failed
        """
        existing_user = self.user_repo.get_user_by_email(email)
        if existing_user:
            logger.warning("register_failed", email=email, reason="email_already_registered")
            raise ValidationError("Email already registered")

        hashed_pwd = hash_password(password)
        user_data = {
            "email": email,
            "hashed_password": hashed_pwd,
            "name": name,
            "providers": ["email"],
            "email_verified": False,
        }

        new_user = self.user_repo.create_user(user_data)

        access_token = create_access_token(str(new_user.id))
        refresh_token = create_refresh_token(str(new_user.id))

        logger.info("user_registered", email=email, auth_method="email")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_id": str(new_user.id),
            "email": new_user.email,
        }

    def login(self, email: str, password: str) -> dict:
        """
        Authenticate with email/password.

        Returns:
            dict with access_token, refresh_token, user_id, email
        Raises:
            AuthenticationError (401): invalid credentials or wrong login method
        """
        user = self.user_repo.get_user_by_email(email)
        if not user:
            logger.warning("login_failed", email=email, reason="user_not_found")
            raise AuthenticationError("Invalid email or password")

        if not user.hashed_password:
            logger.warning("login_failed", email=email, reason="no_password_provider")
            raise AuthenticationError("Invalid login method")

        if not verify_password(password, user.hashed_password):
            logger.warning("login_failed", email=email, reason="wrong_password")
            raise AuthenticationError("Invalid email or password")

        access_token = create_access_token(str(user.id))
        refresh_token = create_refresh_token(str(user.id))

        logger.info("login_success", email=email, auth_method="password")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_id": str(user.id),
            "email": user.email,
        }

    def refresh_access_token(self, refresh_token_value: Optional[str]) -> dict:
        """
        Issue a new access token using a valid refresh token.

        Returns:
            dict with access_token, token_type, user_id, email
        Raises:
            AuthenticationError (401): missing / invalid / blacklisted token
        """
        if not refresh_token_value:
            logger.warning("token_refresh_failed", reason="no_refresh_token_cookie")
            raise AuthenticationError("Refresh token not found")

        try:
            payload = verify_refresh_token(refresh_token_value)
            user_id = payload.get("sub")
            jti = payload.get("jti")

            if not user_id or not jti:
                logger.warning("token_refresh_failed", reason="invalid_payload")
                raise AuthenticationError("Invalid refresh token")

            if self.token_blacklist_repo.is_token_blacklisted(jti):
                logger.warning("token_refresh_failed", reason="token_blacklisted")
                raise AuthenticationError("Token has been revoked")

            user = self.user_repo.get_user_by_id(user_id)
            if not user:
                logger.warning("token_refresh_failed", reason="user_not_found")
                raise AuthenticationError("User not found")

            new_access_token = create_access_token(str(user.id))

            logger.info("token_refreshed")

            return {
                "access_token": new_access_token,
                "token_type": "bearer",
                "user_id": str(user.id),
                "email": user.email,
            }

        except AppException:
            raise
        except JWTError:
            logger.warning("token_refresh_failed", reason="jwt_error")
            raise AuthenticationError("Invalid refresh token")

    def signout(self, refresh_token_value: Optional[str]) -> None:
        """
        Blacklist the refresh token (best-effort). Cookie removal is handled by the router.

        Never raises — failure to blacklist is silently ignored so the sign-out
        response is always successful from the client's perspective.
        """
        logger.info("signout")

        if not refresh_token_value:
            return

        try:
            payload = verify_refresh_token(refresh_token_value)
            refresh_jti = payload.get("jti")
            refresh_exp_timestamp = payload.get("exp")
            user_id = payload.get("sub")

            if refresh_jti and refresh_exp_timestamp and user_id:
                refresh_exp = datetime.fromtimestamp(refresh_exp_timestamp, tz=timezone.utc)
                self.token_blacklist_repo.add_token_to_blacklist(
                    token_jti=refresh_jti,
                    user_id=user_id,
                    token_type="refresh",
                    expires_at=refresh_exp,
                )
        except (JWTError, Exception):
            pass  # Cookie is cleared by the router regardless

    def get_user_info(self, user_id: str) -> dict:
        """
        Retrieve authenticated user's profile data.

        Returns:
            dict with user_id, email, name, avatar_url, providers, email_verified, created_at
        Raises:
            AuthenticationError (401): user not found
        """
        user = self.user_repo.get_user_by_id(user_id)
        if not user:
            raise AuthenticationError("User not found")

        return {
            "user_id": str(user.id),
            "email": user.email,
            "name": user.name,
            "avatar_url": user.avatar_url,
            "providers": user.providers or [],
            "email_verified": user.email_verified,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }

    def check_providers(self, email: str) -> list:
        """
        Return the list of auth providers registered for an email.

        If the email is not registered, all providers are considered available.
        Never raises.
        """
        user = self.user_repo.get_user_by_email(email)
        if not user:
            return ["email", "google"]
        return user.providers or []

    async def handle_google_callback(self, code: str) -> dict:
        """
        Process the Google OAuth callback: exchange code → get user info → upsert user → issue tokens.

        Returns:
            dict with access_token, refresh_token, user_id, email
        Raises:
            Exception: propagated so the router can redirect to the error page
        """
        token_data = await exchange_google_code_for_token(code)
        if not token_data:
            raise AppException("oauth_failed")

        google_access_token = token_data.get("access_token")
        user_info = await get_google_user_info(google_access_token)
        if not user_info:
            raise AppException("user_info_failed")

        email = user_info.get("email")
        provider_user_id = user_info.get("id")
        name = user_info.get("name")
        avatar_url = user_info.get("picture")

        if not email or not provider_user_id:
            raise AppException("missing_user_data")

        user, is_new = get_or_create_oauth_user(
            email=email,
            provider="google",
            provider_user_id=provider_user_id,
            name=name,
            avatar_url=avatar_url,
            db=self.user_repo.db,
        )

        if not user:
            raise AppException("user_creation_failed")

        access_token = create_access_token(str(user.id))
        refresh_token = create_refresh_token(str(user.id))

        logger.info("oauth_callback_success", provider="google", email=email, is_new_user=is_new)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_id": str(user.id),
            "email": email,
        }

    async def request_password_reset(self, email: str) -> None:
        """
        Send a password-reset email if the account exists with email provider.

        Returns silently for non-existent or non-email accounts (avoids email
        enumeration). May raise DatabaseError if token creation fails.
        """
        user = self.user_repo.get_user_by_email(email)
        if not user:
            return

        if "email" not in (user.providers or []):
            return

        token_str = self.password_reset_repo.create_token(
            str(user.id),
            expires_minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES,
        )

        reset_link = f"{FRONTEND_URL}/reset-password?token={token_str}"
        await self.email_service.send_password_reset_email(user.email, reset_link)

        logger.info("password_reset_requested", email=email)

    def verify_password_reset_token(self, token: str) -> None:
        """
        Validate that a password-reset token is still usable.

        Raises:
            ValidationError (422): token invalid or expired
        """
        token_record = self.password_reset_repo.get_valid_token(token)
        if not token_record:
            raise ValidationError("Invalid or expired reset link.")

    def reset_password(self, token: str, new_password: str) -> None:
        """
        Apply a new password using a valid reset token.

        Raises:
            ValidationError (422): token invalid or expired
            DatabaseError (500): password update failed
        """
        token_record = self.password_reset_repo.get_valid_token(token)
        if not token_record:
            raise ValidationError("Invalid or expired reset link. Please request a new one.")

        hashed_pwd = hash_password(new_password)
        updated = self.user_repo.update_user(str(token_record.user_id), {"hashed_password": hashed_pwd})
        if not updated:
            raise DatabaseError("Failed to update password.")

        self.password_reset_repo.mark_token_used(token)

        logger.info("password_reset_completed", user_id=str(token_record.user_id))
