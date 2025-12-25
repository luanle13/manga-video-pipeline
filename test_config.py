import asyncio
from src.config import get_settings, get_credentials


def test_config():
    """Test that the new config system works."""
    # Get settings instance
    settings = get_settings()
    
    # Test database settings
    print(f"Database URL: {settings.database.url}")
    
    # Test OpenAI settings
    print(f"OpenAI Model: {settings.openai.model}")
    print(f"TTS Model: {settings.openai.tts_model}")
    
    # Test YouTube settings
    print(f"EN YouTube Channel: {settings.youtube.en_channel_id}")
    print(f"VN YouTube Channel: {settings.youtube.vn_channel_id}")
    
    # Test getting credentials
    en_creds = get_credentials("en")
    print(f"EN YouTube Client ID: {en_creds['youtube']['client_id']}")
    
    vn_creds = get_credentials("vn")
    print(f"VN YouTube Client ID: {vn_creds['youtube']['client_id']}")
    
    print("Config system works correctly!")


if __name__ == "__main__":
    test_config()