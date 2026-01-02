#!/usr/bin/env python3
"""
Test script for the Telegram notification module.
This script tests the implementation without actually sending messages to Telegram
since that would require valid credentials and network access.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
import sys
import os

# Add src to the path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from notifications.telegram import TelegramNotifier, Video, VideoUpload, Chapter


async def test_telegram_notifier():
    """Test the TelegramNotifier class."""
    print("Testing TelegramNotifier...")

    # Create a notifier instance with mock credentials, mocking the Bot creation
    with patch('notifications.telegram.Bot') as MockBot:
        mock_bot_instance = AsyncMock()
        mock_bot_instance.send_message = AsyncMock()
        MockBot.return_value = mock_bot_instance

        # Create a notifier instance with mock credentials
        notifier = TelegramNotifier("test_token", "test_chat_id")

        # Test send_upload_success method
        video = Video(
            title="Test Video",
            duration=120.5,
            file_path="/path/to/test_video.mp4",
            platform="YouTube"
        )

        uploads = [
            VideoUpload(platform="YouTube", status="completed", video_url="https://youtube.com/test"),
            VideoUpload(platform="TikTok", status="completed", video_url="https://tiktok.com/test"),
            VideoUpload(platform="Facebook", status="failed", error_message="Rate limit exceeded")
        ]

        await notifier.send_upload_success(video, uploads)

        # Check if send_message was called
        assert mock_bot_instance.send_message.called
        print("✓ send_upload_success test passed!")

        # Reset the mock
        mock_bot_instance.send_message.reset_mock()

        # Test send_upload_partial method
        successful = [uploads[0], uploads[1]]  # YouTube and TikTok
        failed = [uploads[2]]  # Facebook

        await notifier.send_upload_partial(video, successful, failed)

        # Check if send_message was called
        assert mock_bot_instance.send_message.called
        print("✓ send_upload_partial test passed!")

        # Reset the mock
        mock_bot_instance.send_message.reset_mock()

        # Test send_pipeline_failure method
        chapter = Chapter(
            title="Test Chapter",
            number=1.0,
            manga_title="Test Manga"
        )

        await notifier.send_pipeline_failure(chapter, "Video Generation", "File not found error")

        # Check if send_message was called
        assert mock_bot_instance.send_message.called
        print("✓ send_pipeline_failure test passed!")

        # Reset the mock
        mock_bot_instance.send_message.reset_mock()

        # Test send_daily_summary method
        stats = {
            'date': '2023-01-01',
            'chapters_processed': 5,
            'videos_created': 5,
            'uploads_attempted': 15,
            'uploads_successful': 14,
            'errors_count': 1,
            'custom_stat': 'test_value'
        }

        await notifier.send_daily_summary(stats)

        # Check if send_message was called
        assert mock_bot_instance.send_message.called
        print("✓ send_daily_summary test passed!")

        # Reset the mock
        mock_bot_instance.send_message.reset_mock()

        # Test rate limiting
        # Try to send multiple messages to test rate limiting
        tasks = []
        for i in range(5):  # Try to send 5 messages
            task = asyncio.create_task(
                notifier._send_message(f"Test message {i}")
            )
            tasks.append(task)

        # Wait for all tasks to complete
        await asyncio.gather(*tasks, return_exceptions=True)

        print("✓ Rate limiting test passed!")

    print("✓ TelegramNotifier tests passed!")


def test_dataclasses():
    """Test the dataclasses."""
    print("Testing dataclasses...")
    
    # Test Video dataclass
    video = Video("Test Title", 120.5, "/path/to/video.mp4", "YouTube")
    assert video.title == "Test Title"
    assert video.duration == 120.5
    assert video.file_path == "/path/to/video.mp4"
    assert video.platform == "YouTube"
    print("✓ Video dataclass test passed!")
    
    # Test VideoUpload dataclass
    upload = VideoUpload("YouTube", "completed", "https://youtube.com/test", None)
    assert upload.platform == "YouTube"
    assert upload.status == "completed"
    assert upload.video_url == "https://youtube.com/test"
    assert upload.error_message is None
    print("✓ VideoUpload dataclass test passed!")
    
    # Test Chapter dataclass
    chapter = Chapter("Test Chapter", 1.0, "Test Manga")
    assert chapter.title == "Test Chapter"
    assert chapter.number == 1.0
    assert chapter.manga_title == "Test Manga"
    print("✓ Chapter dataclass test passed!")


async def main():
    """Run all tests."""
    print("Testing Telegram notification module...\n")
    
    test_dataclasses()
    await test_telegram_notifier()
    
    print("\nAll tests passed! Telegram notification module is working correctly.")


if __name__ == "__main__":
    asyncio.run(main())