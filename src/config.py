from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Any
from functools import cache


class DatabaseSettings(BaseSettings):
    url: str = Field(default="sqlite:///./manga_pipeline.db", env="DATABASE_URL")


class OpenAISettings(BaseSettings):
    api_key: str = Field(default="", env="OPENAI_API_KEY")
    model: str = Field(default="gpt-4o", env="OPENAI_MODEL")
    tts_model: str = Field(default="tts-1", env="TTS_MODEL")
    tts_voice: str = Field(default="alloy", env="TTS_VOICE")


class YouTubeSettings(BaseSettings):
    # English YouTube settings
    en_client_id: str = Field(default="", env="YOUTUBE_EN_CLIENT_ID")
    en_client_secret: str = Field(default="", env="YOUTUBE_EN_CLIENT_SECRET")
    en_channel_id: str = Field(default="", env="YOUTUBE_EN_CHANNEL_ID")
    en_credentials_path: str = Field(default="./credentials/youtube_en_credentials.json", env="YOUTUBE_EN_CREDENTIALS_PATH")
    
    # Vietnamese YouTube settings
    vn_client_id: str = Field(default="", env="YOUTUBE_VN_CLIENT_ID")
    vn_client_secret: str = Field(default="", env="YOUTUBE_VN_CLIENT_SECRET")
    vn_channel_id: str = Field(default="", env="YOUTUBE_VN_CHANNEL_ID")
    vn_credentials_path: str = Field(default="./credentials/youtube_vn_credentials.json", env="YOUTUBE_VN_CREDENTIALS_PATH")


class TikTokSettings(BaseSettings):
    # English TikTok settings
    en_client_key: str = Field(default="", env="TIKTOK_EN_CLIENT_KEY")
    en_client_secret: str = Field(default="", env="TIKTOK_EN_CLIENT_SECRET")
    en_access_token: str = Field(default="", env="TIKTOK_EN_ACCESS_TOKEN")
    
    # Vietnamese TikTok settings
    vn_client_key: str = Field(default="", env="TIKTOK_VN_CLIENT_KEY")
    vn_client_secret: str = Field(default="", env="TIKTOK_VN_CLIENT_SECRET")
    vn_access_token: str = Field(default="", env="TIKTOK_VN_ACCESS_TOKEN")


class FacebookSettings(BaseSettings):
    # English Facebook settings
    en_page_id: str = Field(default="", env="FACEBOOK_EN_PAGE_ID")
    en_access_token: str = Field(default="", env="FACEBOOK_EN_ACCESS_TOKEN")
    
    # Vietnamese Facebook settings
    vn_page_id: str = Field(default="", env="FACEBOOK_VN_PAGE_ID")
    vn_access_token: str = Field(default="", env="FACEBOOK_VN_ACCESS_TOKEN")


class TelegramSettings(BaseSettings):
    bot_token: str = Field(default="", env="TELEGRAM_BOT_TOKEN")
    chat_id: str = Field(default="", env="TELEGRAM_CHAT_ID")
    enabled: bool = Field(default=False, env="TELEGRAM_ENABLED")


class RedisSettings(BaseSettings):
    url: str = Field(default="redis://localhost:6379", env="REDIS_URL")


class PipelineSettings(BaseSettings):
    max_chapters_per_day: int = Field(default=10, env="MAX_CHAPTERS_PER_DAY")
    video_max_duration: int = Field(default=600, env="VIDEO_MAX_DURATION")  # in seconds
    temp_path: str = Field(default="data/temp", env="TEMP_PATH")
    output_path: str = Field(default="data/output", env="OUTPUT_PATH")
    languages: list[str] = Field(default=["en", "vn"], env="LANGUAGES")
    platforms: list[str] = Field(default=["youtube", "tiktok", "facebook"], env="PLATFORMS")


class Settings(BaseSettings):
    database: DatabaseSettings = DatabaseSettings()
    openai: OpenAISettings = OpenAISettings()
    youtube: YouTubeSettings = YouTubeSettings()
    tiktok: TikTokSettings = TikTokSettings()
    facebook: FacebookSettings = FacebookSettings()
    telegram: TelegramSettings = TelegramSettings()
    redis: RedisSettings = RedisSettings()
    pipeline: PipelineSettings = PipelineSettings()

    class Config:
        env_file = ".env"


@cache
def get_settings() -> Settings:
    """Cached function to get settings instance."""
    return Settings()


def get_credentials(language: str) -> dict[str, Any]:
    """
    Get credentials for the specified language.
    
    Args:
        language: Language code ('en' or 'vn')
        
    Returns:
        Dictionary containing credentials for all platforms
    """
    settings = get_settings()
    
    credentials = {}
    
    # YouTube credentials
    if language == "en":
        credentials["youtube"] = {
            "client_id": settings.youtube.en_client_id,
            "client_secret": settings.youtube.en_client_secret,
            "channel_id": settings.youtube.en_channel_id,
            "credentials_path": settings.youtube.en_credentials_path
        }
    elif language == "vn":
        credentials["youtube"] = {
            "client_id": settings.youtube.vn_client_id,
            "client_secret": settings.youtube.vn_client_secret,
            "channel_id": settings.youtube.vn_channel_id,
            "credentials_path": settings.youtube.vn_credentials_path
        }
    else:
        raise ValueError(f"Unsupported language: {language}")
    
    # TikTok credentials
    if language == "en":
        credentials["tiktok"] = {
            "client_key": settings.tiktok.en_client_key,
            "client_secret": settings.tiktok.en_client_secret,
            "access_token": settings.tiktok.en_access_token
        }
    elif language == "vn":
        credentials["tiktok"] = {
            "client_key": settings.tiktok.vn_client_key,
            "client_secret": settings.tiktok.vn_client_secret,
            "access_token": settings.tiktok.vn_access_token
        }
    
    # Facebook credentials
    if language == "en":
        credentials["facebook"] = {
            "page_id": settings.facebook.en_page_id,
            "access_token": settings.facebook.en_access_token
        }
    elif language == "vn":
        credentials["facebook"] = {
            "page_id": settings.facebook.vn_page_id,
            "access_token": settings.facebook.vn_access_token
        }
    
    return credentials


# For backward compatibility, create a global settings instance
settings = get_settings()