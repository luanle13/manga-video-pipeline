#!/usr/bin/env python3
"""
Interactive CLI script to set up YouTube OAuth credentials.
This script guides the user through the YouTube OAuth setup process.
"""

import asyncio
import os
from pathlib import Path
import sys


async def main():
    """Main function for YouTube OAuth setup."""
    print("=== YouTube OAuth Setup ===\n")
    
    print("Step 1: Create a Google Cloud project and enable the YouTube Data API v3")
    print("- Go to: https://console.cloud.google.com/")
    print("- Create a new project or select an existing one")
    print("- Enable the YouTube Data API v3 for your project")
    print("- Go to 'Credentials' section and create credentials")
    print("- Select 'OAuth client ID' and choose 'Desktop application'")
    print("- Download the credentials JSON file\n")
    
    # Get the client secrets file path
    while True:
        client_secrets_path = input("Enter the path to your downloaded client_secrets.json file: ").strip()
        
        if not client_secrets_path:
            print("Please provide a valid path to the client_secrets.json file.")
            continue
        
        client_secrets_path = Path(client_secrets_path).expanduser()
        
        if not client_secrets_path.exists():
            print(f"File not found: {client_secrets_path}")
            continue
        
        break
    
    print("\nStep 2: Setting up YouTube authentication\n")
    
    # Import here to avoid issues if dependencies are not installed
    try:
        from src.uploader.auth.youtube_auth import YouTubeAuth
    except ImportError as e:
        print(f"Error importing YouTubeAuth: {e}")
        print("Make sure you have installed the required dependencies:")
        print("pip install google-api-python-client google-auth google-auth-oauthlib aiofiles")
        return 1
    
    # Get language preference
    while True:
        lang = input("Select language for the channel (en/vn): ").strip().lower()
        if lang in ['en', 'vn']:
            break
        print("Please enter 'en' for English or 'vn' for Vietnamese")
    
    # Determine credentials path based on language
    if lang == 'en':
        credentials_path = "credentials/youtube_en_credentials.json"
        print("\nSetting up for English YouTube channel...")
    else:
        credentials_path = "credentials/youtube_vn_credentials.json"
        print("\nSetting up for Vietnamese YouTube channel...")
    
    # Create auth instance
    auth = YouTubeAuth(credentials_path)
    
    # Attempt to load existing credentials
    if await auth.load_credentials():
        print("Existing credentials found. Checking validity...")
        if await auth.is_token_valid():
            print("Existing credentials are still valid!")
            
            creds_dict = await auth.get_credentials_dict()
            if creds_dict:
                print("Credentials are valid and ready to use.")
                
                # Ask if user wants to refresh anyway
                refresh = input("Would you like to refresh the credentials anyway? (y/N): ").strip().lower()
                if refresh != 'y':
                    print("Using existing valid credentials.")
                    return 0
        else:
            print("Existing credentials are expired or invalid.")
    
    # Perform the authentication
    print("\nStarting OAuth flow. Your browser will open to complete authentication...")
    print("Please log in to your YouTube account and grant the requested permissions.\n")
    
    try:
        success = await auth.authenticate(client_secrets_path)
        if success:
            print("\nAuthentication successful!")
            print(f"Credentials saved to: {credentials_path}")
            
            # Validate the credentials
            if await auth.is_token_valid():
                print("Credentials validated successfully.")
                
                # Display some basic info
                creds_dict = await auth.get_credentials_dict()
                if creds_dict and creds_dict.get('access_token'):
                    print("You're now ready to upload to YouTube!")
                    return 0
                else:
                    print("Warning: Could not retrieve credentials after authentication.")
                    return 1
            else:
                print("Warning: Credentials saved but could not be validated.")
                return 1
        else:
            print("Authentication failed.")
            return 1
    except KeyboardInterrupt:
        print("\nSetup interrupted by user.")
        return 1
    except Exception as e:
        print(f"An error occurred during setup: {e}")
        return 1


if __name__ == "__main__":
    # Create credentials directory if it doesn't exist
    credentials_dir = Path("credentials")
    credentials_dir.mkdir(exist_ok=True)
    
    # Run the async main function
    sys.exit(asyncio.run(main()))