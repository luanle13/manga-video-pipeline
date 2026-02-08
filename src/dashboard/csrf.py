"""CSRF protection for admin dashboard."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict

from src.common.logging_config import setup_logger

logger = setup_logger(__name__)


class CSRFManager:
    """
    Simple CSRF token manager.

    Generates and validates CSRF tokens with expiration.
    Uses in-memory storage (suitable for single-instance deployments).
    """

    def __init__(self, token_lifetime_minutes: int = 60):
        """
        Initialize CSRF manager.

        Args:
            token_lifetime_minutes: Token validity duration in minutes.
        """
        self.token_lifetime = timedelta(minutes=token_lifetime_minutes)
        self._tokens: Dict[str, datetime] = {}

        logger.info(
            "CSRF manager initialized",
            extra={"token_lifetime_minutes": token_lifetime_minutes},
        )

    def generate_token(self) -> str:
        """
        Generate a new CSRF token.

        Returns:
            Random CSRF token string.
        """
        # Generate cryptographically secure random token
        token = secrets.token_urlsafe(32)

        # Store token with expiration time
        self._tokens[token] = datetime.now(timezone.utc)

        # Clean up old tokens (keep last 1000 only)
        if len(self._tokens) > 1000:
            self._cleanup_tokens()

        logger.debug("CSRF token generated")

        return token

    def verify_token(self, token: str) -> bool:
        """
        Verify a CSRF token.

        Args:
            token: Token to verify.

        Returns:
            True if token is valid and not expired, False otherwise.
        """
        if not token or token not in self._tokens:
            logger.warning("CSRF verification failed: token not found")
            return False

        # Check if token expired
        created_at = self._tokens[token]
        age = datetime.now(timezone.utc) - created_at

        if age > self.token_lifetime:
            logger.warning(
                "CSRF verification failed: token expired",
                extra={"age_minutes": age.total_seconds() / 60},
            )
            # Remove expired token
            del self._tokens[token]
            return False

        # Token is valid - remove it (one-time use)
        del self._tokens[token]

        logger.debug("CSRF token verified successfully")

        return True

    def _cleanup_tokens(self):
        """Remove expired tokens to prevent memory buildup."""
        now = datetime.now(timezone.utc)

        # Remove expired tokens
        expired_tokens = [
            token
            for token, created_at in self._tokens.items()
            if (now - created_at) > self.token_lifetime
        ]

        for token in expired_tokens:
            del self._tokens[token]

        logger.debug(
            "CSRF token cleanup completed",
            extra={"removed": len(expired_tokens), "remaining": len(self._tokens)},
        )
