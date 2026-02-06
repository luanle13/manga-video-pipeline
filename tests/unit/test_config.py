"""Tests for configuration module."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.common.config import Settings, get_settings


class TestSettings:
    """Tests for Settings class."""

    def test_defaults_load_correctly(self):
        """Test that default values are loaded correctly."""
        with patch.dict(os.environ, {"S3_BUCKET": "test-bucket"}, clear=False):
            settings = Settings()

        assert settings.aws_region == "ap-southeast-1"
        assert settings.s3_bucket == "test-bucket"
        assert settings.dynamodb_jobs_table == "manga_jobs"
        assert settings.dynamodb_manga_table == "processed_manga"
        assert settings.dynamodb_settings_table == "settings"
        assert settings.deepinfra_secret_name == "manga-pipeline/deepinfra-api-key"
        assert settings.youtube_secret_name == "manga-pipeline/youtube-oauth"
        assert settings.admin_secret_name == "manga-pipeline/admin-credentials"
        assert settings.mangadex_base_url == "https://api.mangadex.org"
        assert settings.deepinfra_base_url == "https://api.deepinfra.com/v1/openai"
        assert settings.default_voice_id == "vi-VN-HoaiMyNeural"
        assert settings.default_tone == "engaging and informative"
        assert settings.default_daily_quota == 1

    def test_env_var_overrides_work(self):
        """Test that environment variables override defaults."""
        env_overrides = {
            "S3_BUCKET": "my-custom-bucket",
            "AWS_REGION": "us-west-2",
            "DYNAMODB_JOBS_TABLE": "custom_jobs",
            "DYNAMODB_MANGA_TABLE": "custom_manga",
            "DYNAMODB_SETTINGS_TABLE": "custom_settings",
            "DEEPINFRA_SECRET_NAME": "custom/deepinfra",
            "YOUTUBE_SECRET_NAME": "custom/youtube",
            "ADMIN_SECRET_NAME": "custom/admin",
            "MANGADEX_BASE_URL": "https://custom.mangadex.org",
            "DEEPINFRA_BASE_URL": "https://custom.deepinfra.com",
            "DEFAULT_VOICE_ID": "en-US-CustomVoice",
            "DEFAULT_TONE": "casual and fun",
            "DEFAULT_DAILY_QUOTA": "5",
        }

        with patch.dict(os.environ, env_overrides, clear=False):
            settings = Settings()

        assert settings.s3_bucket == "my-custom-bucket"
        assert settings.aws_region == "us-west-2"
        assert settings.dynamodb_jobs_table == "custom_jobs"
        assert settings.dynamodb_manga_table == "custom_manga"
        assert settings.dynamodb_settings_table == "custom_settings"
        assert settings.deepinfra_secret_name == "custom/deepinfra"
        assert settings.youtube_secret_name == "custom/youtube"
        assert settings.admin_secret_name == "custom/admin"
        assert settings.mangadex_base_url == "https://custom.mangadex.org"
        assert settings.deepinfra_base_url == "https://custom.deepinfra.com"
        assert settings.default_voice_id == "en-US-CustomVoice"
        assert settings.default_tone == "casual and fun"
        assert settings.default_daily_quota == 5

    def test_s3_bucket_required(self):
        """Test that s3_bucket is a required field."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValidationError):
                Settings()


class TestGetSettings:
    """Tests for get_settings function."""

    def test_get_settings_returns_settings_instance(self):
        """Test that get_settings returns a Settings instance."""
        get_settings.cache_clear()
        with patch.dict(os.environ, {"S3_BUCKET": "test-bucket"}, clear=False):
            settings = get_settings()

        assert isinstance(settings, Settings)

    def test_get_settings_is_cached(self):
        """Test that get_settings returns cached instance."""
        get_settings.cache_clear()
        with patch.dict(os.environ, {"S3_BUCKET": "test-bucket"}, clear=False):
            settings1 = get_settings()
            settings2 = get_settings()

        assert settings1 is settings2
