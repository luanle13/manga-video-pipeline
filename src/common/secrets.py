"""Secrets Manager helper for loading API keys and credentials."""

import json
import time
from typing import Any

import boto3
from botocore.exceptions import ClientError

from src.common.logging_config import setup_logger

logger = setup_logger(__name__)

# Default cache TTL in seconds (5 minutes)
DEFAULT_CACHE_TTL = 300


class SecretNotFoundError(Exception):
    """Raised when a secret is not found."""

    pass


class CachedSecret:
    """Container for cached secret with TTL."""

    def __init__(self, value: Any, ttl: int = DEFAULT_CACHE_TTL) -> None:
        self.value = value
        self.expires_at = time.time() + ttl

    def is_expired(self) -> bool:
        """Check if the cached value has expired."""
        return time.time() >= self.expires_at


class SecretsClient:
    """Client wrapper for AWS Secrets Manager operations."""

    def __init__(self, region: str, cache_ttl: int = DEFAULT_CACHE_TTL) -> None:
        """
        Initialize the Secrets Manager client.

        Args:
            region: AWS region name.
            cache_ttl: Cache TTL in seconds (default: 5 minutes).
        """
        self._region = region
        self._cache_ttl = cache_ttl
        self._client = boto3.client("secretsmanager", region_name=region)
        self._cache: dict[str, CachedSecret] = {}

        logger.info(
            "Secrets Manager client initialized",
            extra={"region": region, "cache_ttl_seconds": cache_ttl},
        )

    def _get_from_cache(self, secret_name: str) -> Any | None:
        """Get secret from cache if available and not expired."""
        cached = self._cache.get(secret_name)
        if cached and not cached.is_expired():
            logger.debug(
                "Secret retrieved from cache",
                extra={"secret_name": secret_name},
            )
            return cached.value
        return None

    def _set_cache(self, secret_name: str, value: Any) -> None:
        """Store secret in cache."""
        self._cache[secret_name] = CachedSecret(value, self._cache_ttl)

    def clear_cache(self, secret_name: str | None = None) -> None:
        """
        Clear the secret cache.

        Args:
            secret_name: Specific secret to clear, or None to clear all.
        """
        if secret_name:
            self._cache.pop(secret_name, None)
            logger.debug("Cache cleared for secret", extra={"secret_name": secret_name})
        else:
            self._cache.clear()
            logger.debug("All secrets cache cleared")

    def get_secret_string(self, secret_name: str) -> str:
        """
        Retrieve a secret string from Secrets Manager.

        Args:
            secret_name: Name or ARN of the secret.

        Returns:
            The secret string value.

        Raises:
            SecretNotFoundError: If the secret doesn't exist.
        """
        # Check cache first
        cached = self._get_from_cache(secret_name)
        if cached is not None:
            return cached

        logger.info(
            "Retrieving secret from Secrets Manager",
            extra={"secret_name": secret_name},
        )

        try:
            response = self._client.get_secret_value(SecretId=secret_name)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "ResourceNotFoundException":
                logger.error(
                    "Secret not found",
                    extra={"secret_name": secret_name},
                )
                raise SecretNotFoundError(f"Secret not found: {secret_name}") from e
            logger.error(
                "Error retrieving secret",
                extra={"secret_name": secret_name, "error_code": error_code},
            )
            raise

        secret_value = response.get("SecretString", "")
        self._set_cache(secret_name, secret_value)

        logger.info(
            "Secret retrieved successfully",
            extra={"secret_name": secret_name},
        )
        return secret_value

    def get_secret_json(self, secret_name: str) -> dict:
        """
        Retrieve a secret and parse it as JSON.

        Args:
            secret_name: Name or ARN of the secret.

        Returns:
            The secret parsed as a dictionary.

        Raises:
            SecretNotFoundError: If the secret doesn't exist.
            json.JSONDecodeError: If the secret is not valid JSON.
        """
        # Check cache for parsed JSON
        cache_key = f"{secret_name}:json"
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        secret_string = self.get_secret_string(secret_name)
        parsed = json.loads(secret_string)

        # Cache the parsed JSON separately
        self._set_cache(cache_key, parsed)

        logger.debug(
            "Secret parsed as JSON",
            extra={"secret_name": secret_name},
        )
        return parsed

    def get_deepinfra_api_key(self, secret_name: str) -> str:
        """
        Retrieve the DeepInfra API key.

        Args:
            secret_name: Name of the secret containing the API key.

        Returns:
            The API key string.
        """
        logger.info(
            "Retrieving DeepInfra API key",
            extra={"secret_name": secret_name},
        )

        secret_data = self.get_secret_json(secret_name)
        api_key = secret_data.get("api_key", "")

        if not api_key:
            # Try alternative key names
            api_key = secret_data.get("apiKey", "") or secret_data.get("API_KEY", "")

        if not api_key:
            logger.warning(
                "API key field not found in secret",
                extra={"secret_name": secret_name},
            )

        return api_key

    def get_youtube_oauth_tokens(self, secret_name: str) -> dict:
        """
        Retrieve YouTube OAuth tokens.

        Args:
            secret_name: Name of the secret containing OAuth tokens.

        Returns:
            Dictionary with client_id, client_secret, refresh_token, access_token.
        """
        logger.info(
            "Retrieving YouTube OAuth tokens",
            extra={"secret_name": secret_name},
        )

        secret_data = self.get_secret_json(secret_name)

        return {
            "client_id": secret_data.get("client_id", ""),
            "client_secret": secret_data.get("client_secret", ""),
            "refresh_token": secret_data.get("refresh_token", ""),
            "access_token": secret_data.get("access_token", ""),
        }

    def update_secret_json(self, secret_name: str, data: dict) -> None:
        """
        Update a secret with new JSON data.

        Args:
            secret_name: Name or ARN of the secret.
            data: Dictionary to store as the new secret value.
        """
        logger.info(
            "Updating secret",
            extra={"secret_name": secret_name},
        )

        secret_string = json.dumps(data)

        try:
            self._client.put_secret_value(
                SecretId=secret_name,
                SecretString=secret_string,
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            logger.error(
                "Error updating secret",
                extra={"secret_name": secret_name, "error_code": error_code},
            )
            raise

        # Clear cache for this secret
        self.clear_cache(secret_name)
        self.clear_cache(f"{secret_name}:json")

        logger.info(
            "Secret updated successfully",
            extra={"secret_name": secret_name},
        )

    def get_admin_credentials(self, secret_name: str) -> dict:
        """
        Retrieve admin credentials.

        Args:
            secret_name: Name of the secret containing admin credentials.

        Returns:
            Dictionary with username and password_hash.
        """
        logger.info(
            "Retrieving admin credentials",
            extra={"secret_name": secret_name},
        )

        secret_data = self.get_secret_json(secret_name)

        return {
            "username": secret_data.get("username", ""),
            "password_hash": secret_data.get("password_hash", ""),
        }
