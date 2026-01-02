from __future__ import annotations
import asyncio
from typing import Any, List, Dict
from telegram import Bot
from telegram.error import TelegramError
import logging
from dataclasses import dataclass
from datetime import datetime
import math


@dataclass
class Video:
    """Represents a video that was processed."""
    title: str
    duration: float  # in seconds
    file_path: str
    platform: str


@dataclass
class VideoUpload:
    """Represents a video upload result."""
    platform: str
    status: str  # 'completed' or 'failed'
    video_url: str | None = None
    error_message: str | None = None


@dataclass
class Chapter:
    """Represents a manga chapter that was processed."""
    title: str
    number: float
    manga_title: str


class TelegramNotifier:
    """Telegram notifier using python-telegram-bot async API."""
    
    def __init__(self, bot_token: str, chat_id: str):
        """
        Initialize the Telegram notifier.

        Args:
            bot_token: Telegram bot token
            chat_id: Chat ID to send notifications to
        """
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id
        # Rate limit: max 20 messages per minute
        # Semaphore with 20 permits that refresh every 60 seconds
        self.rate_limit_semaphore = asyncio.Semaphore(20)
        self._rate_limit_lock = asyncio.Lock()
        # Start rate limiting background task
        asyncio.create_task(self._reset_rate_limit())

    async def _reset_rate_limit(self):
        """Reset the rate limit every minute."""
        while True:
            await asyncio.sleep(60)  # Wait 60 seconds
            async with self._rate_limit_lock:
                # Reset semaphore by creating a new one with 20 permits
                self.rate_limit_semaphore = asyncio.Semaphore(20)
    
    async def _send_message(self, text: str, parse_mode: str = "MarkdownV2") -> bool:
        """Send a message to the Telegram chat with rate limiting.
        
        Args:
            text: Text to send
            parse_mode: Parse mode for formatting (default: MarkdownV2)
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        # Acquire a permit from the semaphore (rate limiting)
        async with self.rate_limit_semaphore:
            try:
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=text,
                    parse_mode=parse_mode,
                    disable_web_page_preview=False
                )
                return True
            except TelegramError as e:
                logging.error(f"Failed to send Telegram message: {e}")
                return False
            except Exception as e:
                logging.error(f"Unexpected error when sending Telegram message: {e}")
                return False
    
    async def send_upload_success(self, video: Video, uploads: List[VideoUpload]) -> None:
        """
        Send notification about successful uploads.
        
        Args:
            video: Video that was uploaded
            uploads: List of upload results
        """
        successful_uploads = [upload for upload in uploads if upload.status == 'completed']
        
        if not successful_uploads:
            return  # No successful uploads to report
        
        # Build the message
        video_emoji = "🎬"
        success_emoji = "✅"
        link_emoji = "🔗"
        
        message = f"{video_emoji} *Upload Success Alert\\!* {video_emoji}\n\n"
        message += f"*Video:* {video.title}\n"
        message += f"*Duration:* {video.duration:.2f}s\n"
        message += f"*File:* `{video.file_path.split('/')[-1]}`\n\n"
        
        message += f"{success_emoji} *Successfully Uploaded To:*\n"
        
        for upload in successful_uploads:
            if upload.video_url:
                message += f"• [{upload.platform}]({upload.video_url})\n"
            else:
                message += f"• {upload.platform}\n"
        
        message += f"\n\\🎉 All platforms uploaded successfully!"
        
        await self._send_message(message)
    
    async def send_upload_partial(self, video: Video, successful: List[VideoUpload], failed: List[VideoUpload]) -> None:
        """
        Send notification about partial upload success.
        
        Args:
            video: Video that was uploaded
            successful: List of successful uploads
            failed: List of failed uploads
        """
        if not successful and not failed:
            return  # Nothing to report
        
        # Build the message
        video_emoji = "🎬"
        success_emoji = "✅"
        fail_emoji = "❌"
        
        message = f"{video_emoji} *Partial Upload Success* {video_emoji}\n\n"
        message += f"*Video:* {video.title}\n"
        message += f"*Duration:* {video.duration:.2f}s\n"
        message += f"*File:* `{video.file_path.split('/')[-1]}`\n\n"
        
        if successful:
            message += f"{success_emoji} *Successfully Uploaded To:*\n"
            for upload in successful:
                if upload.video_url:
                    message += f"• [{upload.platform}]({upload.video_url})\n"
                else:
                    message += f"• {upload.platform}\n"
        
        if failed:
            message += f"\n{fail_emoji} *Failed Uploads:*\n"
            for upload in failed:
                message += f"• {upload.platform} - {upload.error_message or 'Unknown error'}\n"
        
        await self._send_message(message)
    
    async def send_pipeline_failure(self, chapter: Chapter, stage: str, error: str) -> None:
        """
        Send notification about pipeline failure.
        
        Args:
            chapter: Chapter that failed
            stage: Stage where failure occurred
            error: Error message
        """
        fail_emoji = "🚨"
        manga_emoji = "📚"
        
        message = f"{fail_emoji} *PIPELINE FAILURE ALERT* {fail_emoji}\n\n"
        message += f"{manga_emoji} *Manga:* {chapter.manga_title}\n"
        message += f"*Chapter:* {chapter.number}\n"
        message += f"*Title:* {chapter.title}\n"
        message += f"*Stage:* `{stage}`\n\n"
        message += f"*Error:* ```{error[:200]}```\n\n"  # Limit error length
        message += "Please check the logs and resolve the issue\\."
        
        await self._send_message(message)
    
    async def send_daily_summary(self, stats: Dict[str, Any]) -> None:
        """
        Send daily summary statistics.
        
        Args:
            stats: Dictionary containing daily statistics
        """
        chart_emoji = "📊"
        success_emoji = "✅"
        upload_emoji = "📤"
        
        message = f"{chart_emoji} *Daily Summary* {chart_emoji}\n\n"
        
        # Add general stats if available
        if 'date' in stats:
            message += f"*Date:* {stats['date']}\n"
        
        # Add chapter stats
        if 'chapters_processed' in stats:
            manga_emoji = "📚"
            message += f"{manga_emoji} *Chapters Processed:* {stats['chapters_processed']}\n"

        # Add video stats
        if 'videos_created' in stats:
            video_emoji = "🎬"
            message += f"{video_emoji} *Videos Created:* {stats['videos_created']}\n"

        # Add upload stats
        if 'uploads_attempted' in stats:
            upload_emoji = "📤"
            message += f"{upload_emoji} *Uploads Attempted:* {stats['uploads_attempted']}\n"
        if 'uploads_successful' in stats:
            success_emoji = "✅"
            message += f"{success_emoji} *Uploads Successful:* {stats['uploads_successful']}\n"
        
        # Add error stats
        if 'errors_count' in stats:
            error_emoji = "⚠️"
            message += f"{error_emoji} *Errors Encountered:* {stats['errors_count']}\n"
        
        # Add success rate
        if 'uploads_successful' in stats and 'uploads_attempted' in stats and stats['uploads_attempted'] > 0:
            success_rate = (stats['uploads_successful'] / stats['uploads_attempted']) * 100
            message += f"*Success Rate:* {success_rate:.2f}%\n"
        
        # Add additional custom stats if provided
        for key, value in stats.items():
            if key not in ['date', 'chapters_processed', 'videos_created', 'uploads_attempted', 'uploads_successful', 'errors_count']:
                message += f"*{key.replace('_', ' ').title()}:* {value}\n"
        
        message += f"\nKeep up the great work\\!"
        
        await self._send_message(message)