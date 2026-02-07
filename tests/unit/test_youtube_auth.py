"""Unit tests for YouTube OAuth2 token manager."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from google.auth.exceptions import RefreshError

from src.uploader.youtube_auth import YouTubeAuthError, YouTubeAuthManager


@pytest.fixture
def mock_secrets_client():
    """Mock secrets client."""
    return MagicMock()


@pytest.fixture
def valid_tokens():
    """Valid OAuth tokens."""
    return {
        "client_id": "test-client-id.apps.googleusercontent.com",
        "client_secret": "test-client-secret",
        "refresh_token": "test-refresh-token",
        "access_token": "test-access-token",
    }


@pytest.fixture
def youtube_auth(mock_secrets_client):
    """YouTube auth manager instance."""
    return YouTubeAuthManager(mock_secrets_client, "youtube-oauth-secret")


class TestYouTubeAuthManagerInitialization:
    """Tests for YouTubeAuthManager initialization."""

    def test_initializes_successfully(self, mock_secrets_client):
        """Test successful initialization."""
        manager = YouTubeAuthManager(mock_secrets_client, "test-secret")

        assert manager.secrets_client == mock_secrets_client
        assert manager.secret_name == "test-secret"


class TestGetAuthenticatedService:
    """Tests for getting authenticated YouTube service."""

    @patch("src.uploader.youtube_auth.build")
    @patch("src.uploader.youtube_auth.Credentials")
    def test_returns_service_with_valid_token(
        self,
        mock_credentials_class,
        mock_build,
        youtube_auth,
        mock_secrets_client,
        valid_tokens,
    ):
        """Test returning authenticated service with valid access token."""
        # Setup
        mock_secrets_client.get_youtube_oauth_tokens.return_value = valid_tokens

        mock_credentials = MagicMock()
        mock_credentials.valid = True
        mock_credentials.expired = False
        mock_credentials_class.return_value = mock_credentials

        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Execute
        service = youtube_auth.get_authenticated_service()

        # Verify
        assert service == mock_service
        mock_secrets_client.get_youtube_oauth_tokens.assert_called_once_with(
            "youtube-oauth-secret"
        )
        mock_credentials_class.assert_called_once()
        mock_build.assert_called_once_with("youtube", "v3", credentials=mock_credentials)

    @patch("src.uploader.youtube_auth.build")
    @patch("src.uploader.youtube_auth.Credentials")
    @patch("src.uploader.youtube_auth.Request")
    def test_refreshes_expired_token(
        self,
        mock_request_class,
        mock_credentials_class,
        mock_build,
        youtube_auth,
        mock_secrets_client,
        valid_tokens,
    ):
        """Test token refresh when access token is expired."""
        # Setup
        mock_secrets_client.get_youtube_oauth_tokens.return_value = valid_tokens

        mock_credentials = MagicMock()
        mock_credentials.valid = False
        mock_credentials.expired = True
        mock_credentials.refresh_token = "test-refresh-token"
        mock_credentials.token = "new-access-token"
        mock_credentials.expiry = datetime.now(timezone.utc) + timedelta(hours=1)

        # After refresh, credentials become valid
        def refresh_side_effect(request):
            mock_credentials.valid = True

        mock_credentials.refresh.side_effect = refresh_side_effect
        mock_credentials_class.return_value = mock_credentials

        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Execute
        service = youtube_auth.get_authenticated_service()

        # Verify
        assert service == mock_service
        mock_credentials.refresh.assert_called_once()
        mock_build.assert_called_once()

    @patch("src.uploader.youtube_auth.Credentials")
    @patch("src.uploader.youtube_auth.Request")
    def test_updates_secrets_manager_after_refresh(
        self,
        mock_request_class,
        mock_credentials_class,
        youtube_auth,
        mock_secrets_client,
        valid_tokens,
    ):
        """Test that Secrets Manager is updated with new access token after refresh."""
        # Setup
        mock_secrets_client.get_youtube_oauth_tokens.return_value = valid_tokens

        mock_credentials = MagicMock()
        mock_credentials.valid = False
        mock_credentials.expired = True
        mock_credentials.refresh_token = "test-refresh-token"
        mock_credentials.token = "new-access-token"
        mock_credentials.expiry = datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

        def refresh_side_effect(request):
            mock_credentials.valid = True

        mock_credentials.refresh.side_effect = refresh_side_effect
        mock_credentials_class.return_value = mock_credentials

        with patch("src.uploader.youtube_auth.build"):
            # Execute
            youtube_auth.get_authenticated_service()

        # Verify Secrets Manager update
        mock_secrets_client.update_secret_json.assert_called_once()
        call_args = mock_secrets_client.update_secret_json.call_args
        assert call_args[0][0] == "youtube-oauth-secret"

        updated_tokens = call_args[0][1]
        assert updated_tokens["access_token"] == "new-access-token"
        assert "token_expiry" in updated_tokens

    @patch("src.uploader.youtube_auth.Credentials")
    @patch("src.uploader.youtube_auth.Request")
    def test_raises_error_on_refresh_failure(
        self,
        mock_request_class,
        mock_credentials_class,
        youtube_auth,
        mock_secrets_client,
        valid_tokens,
    ):
        """Test error handling when token refresh fails."""
        # Setup
        mock_secrets_client.get_youtube_oauth_tokens.return_value = valid_tokens

        mock_credentials = MagicMock()
        mock_credentials.valid = False
        mock_credentials.expired = True
        mock_credentials.refresh_token = "test-refresh-token"
        mock_credentials.refresh.side_effect = RefreshError("Invalid refresh token")
        mock_credentials_class.return_value = mock_credentials

        # Execute & Verify
        with pytest.raises(YouTubeAuthError, match="Failed to refresh access token"):
            youtube_auth.get_authenticated_service()

    def test_raises_error_on_missing_client_id(
        self,
        youtube_auth,
        mock_secrets_client,
    ):
        """Test error when client_id is missing."""
        # Setup - missing client_id
        mock_secrets_client.get_youtube_oauth_tokens.return_value = {
            "client_id": "",
            "client_secret": "test-secret",
            "refresh_token": "test-refresh",
            "access_token": "test-access",
        }

        # Execute & Verify
        with pytest.raises(YouTubeAuthError, match="Missing required OAuth tokens"):
            youtube_auth.get_authenticated_service()

    def test_raises_error_on_missing_refresh_token(
        self,
        youtube_auth,
        mock_secrets_client,
    ):
        """Test error when refresh_token is missing."""
        # Setup - missing refresh_token
        mock_secrets_client.get_youtube_oauth_tokens.return_value = {
            "client_id": "test-client-id",
            "client_secret": "test-secret",
            "refresh_token": "",
            "access_token": "test-access",
        }

        # Execute & Verify
        with pytest.raises(YouTubeAuthError, match="Missing required OAuth tokens"):
            youtube_auth.get_authenticated_service()

    def test_raises_error_on_secrets_manager_failure(
        self,
        youtube_auth,
        mock_secrets_client,
    ):
        """Test error handling when Secrets Manager fails."""
        # Setup
        mock_secrets_client.get_youtube_oauth_tokens.side_effect = Exception(
            "Secrets Manager error"
        )

        # Execute & Verify
        with pytest.raises(
            YouTubeAuthError, match="Failed to load OAuth tokens from Secrets Manager"
        ):
            youtube_auth.get_authenticated_service()

    @patch("src.uploader.youtube_auth.build")
    @patch("src.uploader.youtube_auth.Credentials")
    def test_raises_error_when_build_fails(
        self,
        mock_credentials_class,
        mock_build,
        youtube_auth,
        mock_secrets_client,
        valid_tokens,
    ):
        """Test error handling when building YouTube service fails."""
        # Setup
        mock_secrets_client.get_youtube_oauth_tokens.return_value = valid_tokens

        mock_credentials = MagicMock()
        mock_credentials.valid = True
        mock_credentials_class.return_value = mock_credentials

        mock_build.side_effect = Exception("API build error")

        # Execute & Verify
        with pytest.raises(YouTubeAuthError, match="Failed to build YouTube service"):
            youtube_auth.get_authenticated_service()

    @patch("src.uploader.youtube_auth.Credentials")
    def test_raises_error_when_credentials_invalid_and_not_refreshable(
        self,
        mock_credentials_class,
        youtube_auth,
        mock_secrets_client,
        valid_tokens,
    ):
        """Test error when credentials are invalid and cannot be refreshed."""
        # Setup
        mock_secrets_client.get_youtube_oauth_tokens.return_value = valid_tokens

        mock_credentials = MagicMock()
        mock_credentials.valid = False
        mock_credentials.expired = False  # Not expired, just invalid
        mock_credentials.refresh_token = None  # No refresh token
        mock_credentials_class.return_value = mock_credentials

        # Execute & Verify
        with pytest.raises(
            YouTubeAuthError, match="OAuth credentials are invalid"
        ):
            youtube_auth.get_authenticated_service()


class TestRefreshToken:
    """Tests for token refresh method."""

    @patch("src.uploader.youtube_auth.Request")
    def test_refreshes_token_successfully(
        self,
        mock_request_class,
        youtube_auth,
        mock_secrets_client,
        valid_tokens,
    ):
        """Test successful token refresh."""
        # Setup
        mock_secrets_client.get_youtube_oauth_tokens.return_value = valid_tokens

        mock_credentials = MagicMock()
        mock_credentials.token = "new-access-token"
        mock_credentials.expiry = datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

        # Execute
        result = youtube_auth.refresh_token(mock_credentials)

        # Verify
        assert result == mock_credentials
        mock_credentials.refresh.assert_called_once()
        mock_secrets_client.update_secret_json.assert_called_once()

    @patch("src.uploader.youtube_auth.Request")
    def test_updates_secrets_manager_with_new_token(
        self,
        mock_request_class,
        youtube_auth,
        mock_secrets_client,
        valid_tokens,
    ):
        """Test that Secrets Manager is updated with new access token."""
        # Setup
        mock_secrets_client.get_youtube_oauth_tokens.return_value = valid_tokens

        mock_credentials = MagicMock()
        mock_credentials.token = "brand-new-access-token"
        mock_credentials.expiry = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        # Execute
        youtube_auth.refresh_token(mock_credentials)

        # Verify
        call_args = mock_secrets_client.update_secret_json.call_args
        assert call_args[0][0] == "youtube-oauth-secret"

        updated_tokens = call_args[0][1]
        assert updated_tokens["access_token"] == "brand-new-access-token"
        assert updated_tokens["token_expiry"] == "2025-01-15T12:00:00+00:00"

    @patch("src.uploader.youtube_auth.Request")
    def test_raises_error_on_refresh_error(
        self,
        mock_request_class,
        youtube_auth,
        mock_secrets_client,
    ):
        """Test error handling when refresh fails with RefreshError."""
        # Setup
        mock_credentials = MagicMock()
        mock_credentials.refresh.side_effect = RefreshError(
            "The refresh token is invalid or revoked"
        )

        # Execute & Verify
        with pytest.raises(
            YouTubeAuthError, match="Failed to refresh access token"
        ):
            youtube_auth.refresh_token(mock_credentials)

    @patch("src.uploader.youtube_auth.Request")
    def test_handles_secrets_manager_update_failure(
        self,
        mock_request_class,
        youtube_auth,
        mock_secrets_client,
        valid_tokens,
    ):
        """Test that token refresh succeeds even if Secrets Manager update fails."""
        # Setup
        mock_secrets_client.get_youtube_oauth_tokens.return_value = valid_tokens
        mock_secrets_client.update_secret_json.side_effect = Exception(
            "Secrets Manager error"
        )

        mock_credentials = MagicMock()
        mock_credentials.token = "new-access-token"
        mock_credentials.expiry = None

        # Execute - should not raise exception
        result = youtube_auth.refresh_token(mock_credentials)

        # Verify
        assert result == mock_credentials
        mock_credentials.refresh.assert_called_once()


class TestTokenSecurity:
    """Tests for token security (no logging of sensitive data)."""

    @patch("src.uploader.youtube_auth.build")
    @patch("src.uploader.youtube_auth.Credentials")
    def test_no_tokens_in_logs(
        self,
        mock_credentials_class,
        mock_build,
        youtube_auth,
        mock_secrets_client,
        valid_tokens,
        caplog,
    ):
        """Test that tokens are never logged."""
        # Setup
        mock_secrets_client.get_youtube_oauth_tokens.return_value = valid_tokens

        mock_credentials = MagicMock()
        mock_credentials.valid = True
        mock_credentials_class.return_value = mock_credentials

        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Execute
        youtube_auth.get_authenticated_service()

        # Verify - check that no tokens appear in logs
        log_output = caplog.text

        # Check that sensitive tokens are not in logs
        assert "test-access-token" not in log_output
        assert "test-refresh-token" not in log_output
        assert "test-client-secret" not in log_output
        assert "test-client-id.apps.googleusercontent.com" not in log_output

    @patch("src.uploader.youtube_auth.Request")
    def test_no_tokens_in_refresh_logs(
        self,
        mock_request_class,
        youtube_auth,
        mock_secrets_client,
        valid_tokens,
        caplog,
    ):
        """Test that tokens are never logged during refresh."""
        # Setup
        mock_secrets_client.get_youtube_oauth_tokens.return_value = valid_tokens

        mock_credentials = MagicMock()
        mock_credentials.token = "super-secret-new-token"
        mock_credentials.expiry = datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

        # Execute
        youtube_auth.refresh_token(mock_credentials)

        # Verify - check that no tokens appear in logs
        log_output = caplog.text

        # Check that sensitive tokens are not in logs
        assert "super-secret-new-token" not in log_output
        assert "test-refresh-token" not in log_output
        assert "test-access-token" not in log_output


class TestCredentialsBuilding:
    """Tests for credentials building logic."""

    @patch("src.uploader.youtube_auth.Credentials")
    def test_builds_credentials_with_correct_parameters(
        self,
        mock_credentials_class,
        youtube_auth,
        mock_secrets_client,
        valid_tokens,
    ):
        """Test that credentials are built with correct parameters."""
        # Setup
        mock_secrets_client.get_youtube_oauth_tokens.return_value = valid_tokens

        mock_credentials = MagicMock()
        mock_credentials.valid = True
        mock_credentials_class.return_value = mock_credentials

        with patch("src.uploader.youtube_auth.build"):
            # Execute
            youtube_auth.get_authenticated_service()

        # Verify
        mock_credentials_class.assert_called_once_with(
            token="test-access-token",
            refresh_token="test-refresh-token",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="test-client-id.apps.googleusercontent.com",
            client_secret="test-client-secret",
            scopes=["https://www.googleapis.com/auth/youtube.upload"],
        )

    @patch("src.uploader.youtube_auth.build")
    @patch("src.uploader.youtube_auth.Credentials")
    def test_builds_youtube_service_with_v3_api(
        self,
        mock_credentials_class,
        mock_build,
        youtube_auth,
        mock_secrets_client,
        valid_tokens,
    ):
        """Test that YouTube service is built with API v3."""
        # Setup
        mock_secrets_client.get_youtube_oauth_tokens.return_value = valid_tokens

        mock_credentials = MagicMock()
        mock_credentials.valid = True
        mock_credentials_class.return_value = mock_credentials

        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Execute
        service = youtube_auth.get_authenticated_service()

        # Verify
        assert service == mock_service
        mock_build.assert_called_once_with("youtube", "v3", credentials=mock_credentials)
