#!/usr/bin/env python3
"""
Interactive CLI script to set up Telegram bot for notifications.
This script guides the user through creating a Telegram bot and getting the necessary credentials.
"""

import asyncio
import os
from pathlib import Path
import sys
import json


async def main():
    """Main function for Telegram bot setup."""
    print("=== Telegram Bot Setup ===\n")
    
    print("Step 1: Create a Telegram bot with BotFather")
    print("- Open Telegram and search for @BotFather")
    print("- Start a chat with BotFather")
    print("- Send /newbot command")
    print("- Follow the instructions to create your bot")
    print("- You'll receive an API token like: 123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ\n")
    
    # Get the bot token
    bot_token = ""
    while not bot_token:
        bot_token = input("Enter your Telegram bot token: ").strip()
        if not bot_token:
            print("Bot token is required. Please try again.")
    
    print(f"\nStep 2: Get your Telegram chat ID")
    print("- Start a chat with your bot (send /start or any message)")
    print("- Visit: https://api.telegram.org/bot{bot_token}/getUpdates")
    print("  (replace {bot_token} with your actual bot token)")
    print("- Look for 'id' in the response under 'message' -> 'from' section")
    print("- The number after 'id': is your chat ID\n")
    
    # Get the chat ID
    chat_id = ""
    while not chat_id:
        chat_id = input("Enter your Telegram chat ID: ").strip()
        if not chat_id:
            print("Chat ID is required. Please try again.")
    
    print(f"\nStep 3: Test the bot connection")
    
    # Import here to avoid issues if dependencies are not installed
    try:
        from telegram import Bot
        from telegram.error import TelegramError
    except ImportError as e:
        print(f"Error importing telegram: {e}")
        print("Make sure you have installed python-telegram-bot:")
        print("pip install python-telegram-bot")
        return 1
    
    # Test the bot
    print("Testing bot connection...")
    bot = Bot(token=bot_token)
    
    try:
        # Get bot info to test the connection
        bot_info = await bot.get_me()
        print(f"Bot connection successful! Bot name: {bot_info.first_name}")
        
        # Send a test message
        test_message = "🚀 Manga Video Pipeline Bot Setup Complete!\n\n"
        test_message += "✅ You will receive notifications about:\n"
        test_message += "• Upload successes and failures\n"
        test_message += "• Pipeline errors and issues\n"
        test_message += "• Daily summary reports\n\n"
        test_message += "Welcome to the notification system!"
        
        await bot.send_message(chat_id=chat_id, text=test_message)
        print("Test message sent successfully!")
        
    except TelegramError as e:
        print(f"Error testing bot: {e}")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1
    
    # Save configuration
    print(f"\nStep 4: Saving configuration")
    
    config = {
        "bot_token": bot_token,
        "chat_id": chat_id,
        "setup_date": str(asyncio.run(asyncio.sleep(0)) if hasattr(asyncio, 'sleep') else str(__import__('datetime').datetime.now()))
    }
    
    # Try to import datetime properly
    from datetime import datetime
    config["setup_date"] = datetime.now().isoformat()
    
    # Create credentials directory if it doesn't exist
    credentials_dir = Path("credentials")
    credentials_dir.mkdir(exist_ok=True)
    
    config_path = credentials_dir / "telegram_config.json"
    
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"Configuration saved to: {config_path}")
        print("\n🎉 Telegram bot setup complete!")
        print("Your bot is now ready to send notifications.")
        
        # Show how to use the bot
        print(f"\nTo use the TelegramNotifier in your code:")
        print(f"```python")
        print(f"from src.notifications.telegram import TelegramNotifier")
        print(f"notifier = TelegramNotifier('{bot_token}', '{chat_id}')")
        print(f"await notifier.send_upload_success(video, uploads)")
        print(f"```")
        
        return 0
        
    except Exception as e:
        print(f"Error saving configuration: {e}")
        return 1


if __name__ == "__main__":
    # Run the async main function
    sys.exit(asyncio.run(main()))