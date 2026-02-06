"""Tests for Secrets Manager helper."""

import json
import os
from collections.abc import Generator
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

from src.common.secrets import SecretNotFoundError, SecretsClient


@pytest.fixture
def aws_credentials() -> Generator[None, None, None]:
    """Mock AWS credentials for moto."""
    with patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "testing",
            "AWS_SECRET_ACCESS_KEY": "testing",
            "AWS_SECURITY_TOKEN": "testing",
            "AWS_SESSION_TOKEN": "testing",
            "AWS_DEFAULT_REGION": "ap-southeast-1",
        },
    ):
        yield


@pytest.fixture
def mock_secretsmanager() -> Generator[None, None, None]:
    """Start moto mock for Secrets Manager."""
    with mock_aws():
        yield


@pytest.fixture
def secrets_client(
    aws_credentials: None, mock_secretsmanager: None
) -> SecretsClient:
    """Create a SecretsClient for testing."""
    return SecretsClient(region="ap-southeast-1", cache_ttl=300)


@pytest.fixture
def sm_client(aws_credentials: None, mock_secretsmanager: None) -> boto3.client:
    """Create a raw Secrets Manager client for test setup."""
    return boto3.client("secretsmanager", region_name="ap-southeast-1")


class TestGetSecretString:
    """Tests for get_secret_string method."""

    def test_create_and_retrieve_secret(
        self, secrets_client: SecretsClient, sm_client: boto3.client
    ) -> None:
        """Test creating and retrieving a secret string."""
        # Create a secret
        secret_name = "test/api-key"
        secret_value = "super-secret-api-key-12345"
        sm_client.create_secret(Name=secret_name, SecretString=secret_value)

        # Retrieve it
        result = secrets_client.get_secret_string(secret_name)

        assert result == secret_value

    def test_retrieve_nonexistent_secret_raises_error(
        self, secrets_client: SecretsClient
    ) -> None:
        """Test that retrieving non-existent secret raises SecretNotFoundError."""
        with pytest.raises(SecretNotFoundError) as exc_info:
            secrets_client.get_secret_string("nonexistent/secret")

        assert "nonexistent/secret" in str(exc_info.value)

    def test_secret_string_with_special_characters(
        self, secrets_client: SecretsClient, sm_client: boto3.client
    ) -> None:
        """Test secret with special characters."""
        secret_name = "test/special"
        secret_value = "pa$$w0rd!@#$%^&*()_+-=[]{}|;':\",./<>?"
        sm_client.create_secret(Name=secret_name, SecretString=secret_value)

        result = secrets_client.get_secret_string(secret_name)

        assert result == secret_value


class TestGetSecretJson:
    """Tests for get_secret_json method."""

    def test_json_secret_roundtrip(
        self, secrets_client: SecretsClient, sm_client: boto3.client
    ) -> None:
        """Test creating and retrieving a JSON secret."""
        secret_name = "test/config"
        secret_data = {
            "api_key": "key123",
            "endpoint": "https://api.example.com",
            "settings": {"timeout": 30, "retries": 3},
        }
        sm_client.create_secret(
            Name=secret_name, SecretString=json.dumps(secret_data)
        )

        result = secrets_client.get_secret_json(secret_name)

        assert result == secret_data

    def test_json_secret_with_list(
        self, secrets_client: SecretsClient, sm_client: boto3.client
    ) -> None:
        """Test JSON secret containing a list."""
        secret_name = "test/list"
        secret_data = {"items": [1, 2, 3], "names": ["a", "b", "c"]}
        sm_client.create_secret(
            Name=secret_name, SecretString=json.dumps(secret_data)
        )

        result = secrets_client.get_secret_json(secret_name)

        assert result == secret_data

    def test_invalid_json_raises_error(
        self, secrets_client: SecretsClient, sm_client: boto3.client
    ) -> None:
        """Test that invalid JSON raises JSONDecodeError."""
        secret_name = "test/invalid-json"
        sm_client.create_secret(Name=secret_name, SecretString="not valid json")

        with pytest.raises(json.JSONDecodeError):
            secrets_client.get_secret_json(secret_name)


class TestCaching:
    """Tests for secret caching."""

    def test_cache_works_second_call_uses_cache(
        self, secrets_client: SecretsClient, sm_client: boto3.client
    ) -> None:
        """Test that second call uses cached value."""
        secret_name = "test/cached"
        secret_value = "cached-value"
        sm_client.create_secret(Name=secret_name, SecretString=secret_value)

        # First call - should hit API
        result1 = secrets_client.get_secret_string(secret_name)

        # Delete the secret from AWS
        sm_client.delete_secret(SecretId=secret_name, ForceDeleteWithoutRecovery=True)

        # Second call - should use cache, not fail
        result2 = secrets_client.get_secret_string(secret_name)

        assert result1 == secret_value
        assert result2 == secret_value

    def test_cache_cleared_on_update(
        self, secrets_client: SecretsClient, sm_client: boto3.client
    ) -> None:
        """Test that cache is cleared when secret is updated."""
        secret_name = "test/update-cache"
        original_data = {"value": "original"}
        sm_client.create_secret(
            Name=secret_name, SecretString=json.dumps(original_data)
        )

        # First retrieval
        result1 = secrets_client.get_secret_json(secret_name)
        assert result1 == original_data

        # Update the secret
        new_data = {"value": "updated"}
        secrets_client.update_secret_json(secret_name, new_data)

        # Should get new value (cache was cleared)
        result2 = secrets_client.get_secret_json(secret_name)
        assert result2 == new_data

    def test_clear_cache_specific_secret(
        self, secrets_client: SecretsClient, sm_client: boto3.client
    ) -> None:
        """Test clearing cache for a specific secret."""
        secret_name = "test/clear-specific"
        sm_client.create_secret(Name=secret_name, SecretString="value")

        # Populate cache
        secrets_client.get_secret_string(secret_name)
        assert secret_name in secrets_client._cache

        # Clear specific secret
        secrets_client.clear_cache(secret_name)
        assert secret_name not in secrets_client._cache

    def test_clear_cache_all(
        self, secrets_client: SecretsClient, sm_client: boto3.client
    ) -> None:
        """Test clearing all cached secrets."""
        secrets = ["test/s1", "test/s2", "test/s3"]
        for name in secrets:
            sm_client.create_secret(Name=name, SecretString="value")
            secrets_client.get_secret_string(name)

        assert len(secrets_client._cache) >= 3

        # Clear all
        secrets_client.clear_cache()
        assert len(secrets_client._cache) == 0


class TestGetDeepinfraApiKey:
    """Tests for get_deepinfra_api_key method."""

    def test_get_deepinfra_api_key(
        self, secrets_client: SecretsClient, sm_client: boto3.client
    ) -> None:
        """Test retrieving DeepInfra API key."""
        secret_name = "manga-pipeline/deepinfra-api-key"
        secret_data = {"api_key": "di-api-key-12345"}
        sm_client.create_secret(
            Name=secret_name, SecretString=json.dumps(secret_data)
        )

        result = secrets_client.get_deepinfra_api_key(secret_name)

        assert result == "di-api-key-12345"

    def test_get_deepinfra_api_key_alternative_field(
        self, secrets_client: SecretsClient, sm_client: boto3.client
    ) -> None:
        """Test retrieving API key with alternative field name."""
        secret_name = "test/alt-key"
        secret_data = {"apiKey": "alt-api-key"}
        sm_client.create_secret(
            Name=secret_name, SecretString=json.dumps(secret_data)
        )

        result = secrets_client.get_deepinfra_api_key(secret_name)

        assert result == "alt-api-key"

    def test_get_deepinfra_api_key_missing_field(
        self, secrets_client: SecretsClient, sm_client: boto3.client
    ) -> None:
        """Test retrieving API key when field is missing."""
        secret_name = "test/no-key"
        secret_data = {"other_field": "value"}
        sm_client.create_secret(
            Name=secret_name, SecretString=json.dumps(secret_data)
        )

        result = secrets_client.get_deepinfra_api_key(secret_name)

        assert result == ""


class TestGetYoutubeOauthTokens:
    """Tests for get_youtube_oauth_tokens method."""

    def test_get_youtube_oauth_tokens(
        self, secrets_client: SecretsClient, sm_client: boto3.client
    ) -> None:
        """Test retrieving YouTube OAuth tokens."""
        secret_name = "manga-pipeline/youtube-oauth"
        secret_data = {
            "client_id": "client-123.apps.googleusercontent.com",
            "client_secret": "GOCSPX-secret123",
            "refresh_token": "1//refresh-token-abc",
            "access_token": "ya29.access-token-xyz",
        }
        sm_client.create_secret(
            Name=secret_name, SecretString=json.dumps(secret_data)
        )

        result = secrets_client.get_youtube_oauth_tokens(secret_name)

        assert result["client_id"] == secret_data["client_id"]
        assert result["client_secret"] == secret_data["client_secret"]
        assert result["refresh_token"] == secret_data["refresh_token"]
        assert result["access_token"] == secret_data["access_token"]

    def test_get_youtube_oauth_tokens_partial(
        self, secrets_client: SecretsClient, sm_client: boto3.client
    ) -> None:
        """Test retrieving partial OAuth tokens."""
        secret_name = "test/partial-oauth"
        secret_data = {
            "client_id": "client-123",
            "client_secret": "secret-456",
        }
        sm_client.create_secret(
            Name=secret_name, SecretString=json.dumps(secret_data)
        )

        result = secrets_client.get_youtube_oauth_tokens(secret_name)

        assert result["client_id"] == "client-123"
        assert result["client_secret"] == "secret-456"
        assert result["refresh_token"] == ""
        assert result["access_token"] == ""


class TestUpdateSecretJson:
    """Tests for update_secret_json method."""

    def test_update_secret_json(
        self, secrets_client: SecretsClient, sm_client: boto3.client
    ) -> None:
        """Test updating a secret with new JSON data."""
        secret_name = "test/update"
        original_data = {"value": "original"}
        sm_client.create_secret(
            Name=secret_name, SecretString=json.dumps(original_data)
        )

        # Update the secret
        new_data = {"value": "updated", "new_field": "added"}
        secrets_client.update_secret_json(secret_name, new_data)

        # Verify update
        result = secrets_client.get_secret_json(secret_name)
        assert result == new_data

    def test_update_oauth_tokens(
        self, secrets_client: SecretsClient, sm_client: boto3.client
    ) -> None:
        """Test updating OAuth tokens (common use case)."""
        secret_name = "test/oauth-update"
        original_tokens = {
            "client_id": "client-123",
            "client_secret": "secret-456",
            "refresh_token": "old-refresh",
            "access_token": "old-access",
        }
        sm_client.create_secret(
            Name=secret_name, SecretString=json.dumps(original_tokens)
        )

        # Simulate token refresh
        updated_tokens = {
            **original_tokens,
            "access_token": "new-access-token",
            "expires_at": 1234567890,
        }
        secrets_client.update_secret_json(secret_name, updated_tokens)

        result = secrets_client.get_secret_json(secret_name)
        assert result["access_token"] == "new-access-token"
        assert result["expires_at"] == 1234567890


class TestGetAdminCredentials:
    """Tests for get_admin_credentials method."""

    def test_get_admin_credentials(
        self, secrets_client: SecretsClient, sm_client: boto3.client
    ) -> None:
        """Test retrieving admin credentials."""
        secret_name = "manga-pipeline/admin-credentials"
        secret_data = {
            "username": "admin",
            "password_hash": "$2b$12$hash123abc",
        }
        sm_client.create_secret(
            Name=secret_name, SecretString=json.dumps(secret_data)
        )

        result = secrets_client.get_admin_credentials(secret_name)

        assert result["username"] == "admin"
        assert result["password_hash"] == "$2b$12$hash123abc"

    def test_get_admin_credentials_missing_fields(
        self, secrets_client: SecretsClient, sm_client: boto3.client
    ) -> None:
        """Test retrieving admin credentials with missing fields."""
        secret_name = "test/empty-admin"
        secret_data = {}
        sm_client.create_secret(
            Name=secret_name, SecretString=json.dumps(secret_data)
        )

        result = secrets_client.get_admin_credentials(secret_name)

        assert result["username"] == ""
        assert result["password_hash"] == ""


class TestClientInitialization:
    """Tests for client initialization."""

    def test_client_initialization(
        self, aws_credentials: None, mock_secretsmanager: None
    ) -> None:
        """Test client initializes with correct region."""
        client = SecretsClient(region="us-west-2")
        assert client._region == "us-west-2"

    def test_client_custom_cache_ttl(
        self, aws_credentials: None, mock_secretsmanager: None
    ) -> None:
        """Test client initializes with custom cache TTL."""
        client = SecretsClient(region="ap-southeast-1", cache_ttl=600)
        assert client._cache_ttl == 600
