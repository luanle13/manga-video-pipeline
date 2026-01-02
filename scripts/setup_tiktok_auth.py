#!/usr/bin/env python3
"""
Interactive CLI script to set up TikTok API credentials.
This script guides the user through the TikTok API authentication process.
"""

import asyncio
import os
from pathlib import Path
import sys


async def main():
    """Main function for TikTok auth setup."""
    print("=== TikTok API Setup ===\n")
    
    print("Step 1: Create a TikTok Developer Account and App")
    print("- Go to: https://developers.tiktok.com/")
    print("- Apply for a developer account if you don't have one")
    print("- Create a new app in the TikTok Developer portal")
    print("- Note down your Client Key and Client Secret\n")
    
    # Get the app credentials
    while True:
        client_key = input("Enter your TikTok Client Key: ").strip()
        
        if not client_key:
            print("Client Key is required. Please try again.")
            continue
        break
    
    while True:
        client_secret = input("Enter your TikTok Client Secret: ").strip()
        
        if not client_secret:
            print("Client Secret is required. Please try again.")
            continue
        break
    
    print("\nStep 2: Set up Redirect URI")
    print("For this setup, we'll use a local server redirect URI.")
    print("Make sure to register this URI in your TikTok app settings.\n")
    
    redirect_uri = "http://localhost:8080/callback"
    print(f"Redirect URI: {redirect_uri}")
    
    print("\nStep 3: Setting up TikTok authentication\n")
    
    # Import here to avoid issues if dependencies are not installed
    try:
        from src.uploader.auth.tiktok_auth import TikTokAuth
    except ImportError as e:
        print(f"Error importing TikTokAuth: {e}")
        print("Make sure you have installed the required dependencies:")
        print("pip install httpx aiofiles")
        return 1
    
    # Get language preference
    while True:
        lang = input("Select language for the account (en/vn): ").strip().lower()
        if lang in ['en', 'vn']:
            break
        print("Please enter 'en' for English or 'vn' for Vietnamese")
    
    # Determine credentials path based on language
    if lang == 'en':
        credentials_path = "credentials/tiktok_en_credentials.json"
        print("\nSetting up for English TikTok account...")
    else:
        credentials_path = "credentials/tiktok_vn_credentials.json"
        print("\nSetting up for Vietnamese TikTok account...")
    
    # Create auth instance
    auth = TikTokAuth(credentials_path)
    
    # Attempt to load existing credentials
    if await auth.load_credentials():
        print("Existing credentials found. Checking validity...")
        if await auth.is_token_valid():
            print("Existing credentials are still valid!")
            
            # Ask if user wants to continue anyway
            refresh = input("Would you like to re-authenticate anyway? (y/N): ").strip().lower()
            if refresh != 'y':
                print("Using existing valid credentials.")
                return 0
        else:
            print("Existing credentials are expired or invalid.")
    
    # Perform the authentication
    print(f"\nStarting OAuth flow for TikTok...")
    print("You will need to:")
    print(f"1. Visit: https://www.tiktok.com/oauth/authorize/")
    print(f"2. Use Client Key: {client_key}")
    print(f"3. Use Redirect URI: {redirect_uri}")
    print(f"4. Grant the necessary permissions")
    print(f"5. Copy the authorization code from the callback URL\n")
    
    try:
        success = await auth.authenticate(client_key, client_secret, redirect_uri)
        if success:
            print("\nAuthentication successful!")
            print(f"Credentials saved to: {credentials_path}")
            
            # Validate the credentials
            if await auth.is_token_valid():
                print("Credentials validated successfully.")
                
                # Display some basic info
                creds_dict = await auth.get_credentials_dict()
                if creds_dict and creds_dict.get('access_token'):
                    print("You're now ready to upload to TikTok!")
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