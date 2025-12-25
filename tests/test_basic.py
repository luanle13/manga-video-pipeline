import pytest
from src.config import get_settings
from src.discovery.manga_discovery import discovery
from src.scraper.manga_scraper import scraper
from src.ai.manga_ai import ai_processor
from src.video.manga_video_generator import video_generator
from src.uploader.video_uploader import uploader
from src.notifications.notification_service import notification_service
from src.database.models import init_db


@pytest.mark.asyncio
async def test_settings_loaded():
    """Test that settings are loaded correctly."""
    settings = get_settings()
    assert settings.database.url is not None
    assert settings.redis.url is not None
    assert settings.openai.api_key is not None


@pytest.mark.asyncio
async def test_discovery_initialization():
    """Test that discovery module is initialized."""
    assert discovery is not None
    assert discovery.client is not None


@pytest.mark.asyncio
async def test_scraper_initialization():
    """Test that scraper module is initialized."""
    assert scraper is not None


@pytest.mark.asyncio
async def test_ai_processor_initialization():
    """Test that AI processor is initialized."""
    assert ai_processor is not None


@pytest.mark.asyncio
async def test_video_generator_initialization():
    """Test that video generator is initialized."""
    assert video_generator is not None


@pytest.mark.asyncio
async def test_uploader_initialization():
    """Test that uploader is initialized."""
    assert uploader is not None


@pytest.mark.asyncio
async def test_notification_service_initialization():
    """Test that notification service is initialized."""
    assert notification_service is not None


def test_database_initialization():
    """Test that database can be initialized."""
    # This just tests that the init_db function runs without error
    init_db()
    assert True  # If we get here, init_db ran successfully


@pytest.mark.asyncio
async def test_discovery_get_trending():
    """Test discovery trending manga functionality (with a basic check)."""
    # This is a basic check that the method exists and can be called
    # In a real test, we would mock the API responses
    trending = await discovery.get_trending_manga()
    # Even if the API call fails, it should return an empty list, not raise an exception
    assert isinstance(trending, list)


if __name__ == "__main__":
    pytest.main([__file__])