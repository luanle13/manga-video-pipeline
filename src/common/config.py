"""Configuration module for manga-video-pipeline."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    aws_region: str = "ap-southeast-1"
    s3_bucket: str
    dynamodb_jobs_table: str = "manga_jobs"
    dynamodb_manga_table: str = "processed_manga"
    dynamodb_settings_table: str = "settings"
    deepinfra_secret_name: str = "manga-pipeline/deepinfra-api-key"
    youtube_secret_name: str = "manga-pipeline/youtube-oauth"
    admin_secret_name: str = "manga-pipeline/admin-credentials"
    mangadex_base_url: str = "https://api.mangadex.org"
    deepinfra_base_url: str = "https://api.deepinfra.com/v1/openai"
    default_voice_id: str = "vi-VN-HoaiMyNeural"
    default_tone: str = "engaging and informative"
    default_daily_quota: int = 1
    daily_quota: int = 10
    max_chapters: int = 10  # Limit chapters per video to avoid Lambda timeout

    model_config = {"env_prefix": "", "case_sensitive": False}


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
