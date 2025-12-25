from telegram import Bot
from telegram.ext import Application
from typing import Any
from ..config import get_settings


class NotificationService:
    """Handle notifications via various channels."""
    
    def __init__(self):
        self.settings = get_settings()
        self.telegram_bot = Bot(token=self.settings.telegram.bot_token) if self.settings.telegram.bot_token else None

    async def send_telegram_notification(self, message: str) -> bool:
        """Send notification via Telegram."""
        if not self.telegram_bot:
            print("Telegram bot token not configured")
            return False
        
        try:
            await self.telegram_bot.send_message(
                chat_id=settings.telegram_chat_id,
                text=message
            )
            return True
        except Exception as e:
            print(f"Error sending Telegram notification: {e}")
            return False

    async def send_pipeline_status(self, pipeline_name: str, status: str, details: dict[str, Any] | None = None) -> bool:
        """Send pipeline status notification."""
        message = f"Pipeline Status Update:\n"
        message += f"Pipeline: {pipeline_name}\n"
        message += f"Status: {status}\n"
        
        if details:
            for key, value in details.items():
                message += f"{key}: {value}\n"
        
        success = True
        if self.telegram_bot:
            success &= await self.send_telegram_notification(message)
        
        return success

    async def send_error_notification(self, error: str, context: str = "") -> bool:
        """Send error notification."""
        message = f"🚨 ERROR ALERT 🚨\n"
        message += f"Context: {context}\n" if context else ""
        message += f"Error: {error}\n"
        
        success = True
        if self.telegram_bot:
            success &= await self.send_telegram_notification(message)
        
        return success


# Global notification service instance
notification_service = NotificationService()