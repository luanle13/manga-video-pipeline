"""YouTube OAuth2 token manager for authenticated API access."""

from datetime import datetime, timezone

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build

from src.common.logging_config import setup_logger
from src.common.secrets import SecretsClient

logger = setup_logger(__name__)


class YouTubeAuthError(Exception):
    """Raised when YouTube authentication fails."""

    pass


class YouTubeAuthManager:
    """Manager for YouTube OAuth2 authentication and token refresh."""

    def __init__(self, secrets_client: SecretsClient, secret_name: str) -> None:
        """
        Initialize the YouTube authentication manager.

        Args:
            secrets_client: Client for accessing Secrets Manager.
            secret_name: Name of the secret containing OAuth tokens.
        """
        self.secrets_client = secrets_client
        self.secret_name = secret_name

        logger.info(
            "YouTubeAuthManager initialized",
            extra={"secret_name": secret_name},
        )

    def get_authenticated_service(self) -> Resource:
        """
        Get an authenticated YouTube API service.

        Loads OAuth tokens from Secrets Manager, refreshes the access token
        if expired, updates Secrets Manager with new tokens, and returns
        an authenticated YouTube service.

        Returns:
            Authenticated YouTube API service (googleapiclient Resource).

        Raises:
            YouTubeAuthError: If authentication fails or tokens are invalid.
        """
        logger.info("Getting authenticated YouTube service")

        # Load OAuth tokens from Secrets Manager
        try:
            tokens = self.secrets_client.get_youtube_oauth_tokens(self.secret_name)
        except Exception as e:
            logger.error(
                "Failed to load OAuth tokens from Secrets Manager",
                extra={"error": str(e)},
                exc_info=True,
            )
            raise YouTubeAuthError(
                "Failed to load OAuth tokens from Secrets Manager"
            ) from e

        # Validate required tokens
        client_id = tokens.get("client_id")
        client_secret = tokens.get("client_secret")
        refresh_token = tokens.get("refresh_token")
        access_token = tokens.get("access_token")

        if not all([client_id, client_secret, refresh_token]):
            logger.error("Missing required OAuth tokens (client_id, client_secret, or refresh_token)")
            raise YouTubeAuthError(
                "Missing required OAuth tokens. Ensure client_id, client_secret, "
                "and refresh_token are set in Secrets Manager."
            )

        # Build credentials from tokens
        credentials = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=["https://www.googleapis.com/auth/youtube.upload"],
        )

        # Check if token needs refresh
        if not credentials.valid:
            if credentials.expired and credentials.refresh_token:
                logger.info("Access token expired, refreshing")
                try:
                    credentials = self.refresh_token(credentials)
                except YouTubeAuthError:
                    raise
                except Exception as e:
                    logger.error(
                        "Unexpected error during token refresh",
                        extra={"error": str(e)},
                        exc_info=True,
                    )
                    raise YouTubeAuthError("Failed to refresh access token") from e
            else:
                logger.error("Credentials are invalid and cannot be refreshed")
                raise YouTubeAuthError(
                    "OAuth credentials are invalid. Access token is missing or expired, "
                    "and no refresh token is available."
                )
        else:
            logger.info("Token valid, no refresh needed")

        # Build YouTube service
        try:
            youtube_service = build("youtube", "v3", credentials=credentials)
            logger.info("YouTube service authenticated successfully")
            return youtube_service
        except Exception as e:
            logger.error(
                "Failed to build YouTube service",
                extra={"error": str(e)},
                exc_info=True,
            )
            raise YouTubeAuthError("Failed to build YouTube service") from e

    def refresh_token(self, credentials: Credentials) -> Credentials:
        """
        Refresh the OAuth access token.

        Args:
            credentials: Google OAuth2 credentials to refresh.

        Returns:
            Updated credentials with new access token.

        Raises:
            YouTubeAuthError: If token refresh fails.
        """
        logger.info("Refreshing OAuth access token")

        try:
            # Force refresh
            credentials.refresh(Request())
            logger.info("Token refreshed successfully")

        except RefreshError as e:
            logger.error(
                "Failed to refresh access token - refresh token may be invalid or revoked",
                extra={"error": str(e)},
            )
            raise YouTubeAuthError(
                "Failed to refresh access token. The refresh token may be invalid or revoked. "
                "Please re-authenticate and update the OAuth tokens in Secrets Manager."
            ) from e

        except Exception as e:
            logger.error(
                "Unexpected error during token refresh",
                extra={"error": str(e)},
                exc_info=True,
            )
            raise YouTubeAuthError("Failed to refresh access token") from e

        # Store updated tokens in Secrets Manager
        try:
            # Load current secret data to preserve all fields
            current_tokens = self.secrets_client.get_youtube_oauth_tokens(
                self.secret_name
            )

            # Update with new access token
            current_tokens["access_token"] = credentials.token

            # Update expiry if available
            if credentials.expiry:
                current_tokens["token_expiry"] = credentials.expiry.isoformat()

            # Store back to Secrets Manager
            self.secrets_client.update_secret_json(self.secret_name, current_tokens)

            logger.info("Updated access token stored in Secrets Manager")

        except Exception as e:
            logger.error(
                "Failed to update access token in Secrets Manager",
                extra={"error": str(e)},
                exc_info=True,
            )
            # Don't raise - the token refresh succeeded, we just failed to persist it
            # The refreshed credentials are still valid for this session
            logger.warning(
                "Token refresh succeeded but failed to persist to Secrets Manager. "
                "The refreshed token will be used for this session only."
            )

        return credentials
