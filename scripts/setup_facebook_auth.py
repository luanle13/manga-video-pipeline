#!/usr/bin/env python3
"""
Interactive CLI script to set up Facebook API credentials.
This script guides the user through the Facebook API authentication process.
"""

import asyncio
import os
from pathlib import Path
import sys


async def main():
    """Main function for Facebook auth setup."""
    print("=== Facebook API Setup ===\n")
    
    print("Step 1: Create a Facebook Developer Account and App")
    print("- Go to: https://developers.facebook.com/")
    print("- Create a new app or select an existing one")
    print("- Note down your App ID and App Secret")
    print("- In your app settings, add 'Facebook Login' as a product")
    print("- Set your redirect URI for OAuth flow\n")
    
    # Get the app credentials
    while True:
        app_id = input("Enter your Facebook App ID: ").strip()
        
        if not app_id:
            print("App ID is required. Please try again.")
            continue
        break
    
    while True:
        app_secret = input("Enter your Facebook App Secret: ").strip()
        
        if not app_secret:
            print("App Secret is required. Please try again.")
            continue
        break
    
    print("\nStep 2: Set up Redirect URI")
    print("For this setup, we'll use a local server redirect URI.")
    print("Make sure to register this URI in your Facebook app settings.\n")
    
    redirect_uri = "https://www.facebook.com/connect/login_success.html"
    print(f"Redirect URI: {redirect_uri}")
    
    print("\nStep 3: Setting up Facebook authentication\n")
    
    # Import here to avoid issues if dependencies are not installed
    try:
        from src.uploader.auth.facebook_auth import FacebookAuth
    except ImportError as e:
        print(f"Error importing FacebookAuth: {e}")
        print("Make sure you have installed the required dependencies:")
        print("pip install httpx aiofiles")
        return 1
    
    # Get language preference
    while True:
        lang = input("Select language for the page (en/vn): ").strip().lower()
        if lang in ['en', 'vn']:
            break
        print("Please enter 'en' for English or 'vn' for Vietnamese")
    
    # Determine credentials path based on language
    if lang == 'en':
        credentials_path = "credentials/facebook_en_credentials.json"
        print("\nSetting up for English Facebook page...")
    else:
        credentials_path = "credentials/facebook_vn_credentials.json"
        print("\nSetting up for Vietnamese Facebook page...")
    
    # Create auth instance
    auth = FacebookAuth(credentials_path)
    
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
    print(f"\nStarting OAuth flow for Facebook...")
    print("You will need to:")
    print(f"1. Visit: https://www.facebook.com/v18.0/dialog/oauth")
    print(f"2. Use App ID: {app_id}")
    print(f"3. Use Redirect URI: {redirect_uri}")
    print(f"4. Grant the necessary permissions (pages_show_list, pages_read_engagement, pages_manage_posts)")
    print(f"5. Copy the full URL after authorization from the callback page\n")
    
    try:
        success = await auth.authenticate(app_id, app_secret, redirect_uri)
        if success:
            print("\nAuthentication successful!")
            print(f"Credentials saved to: {credentials_path}")
            
            # Validate the credentials
            if await auth.is_token_valid():
                print("Credentials validated successfully.")
                
                # Display some basic info
                creds_dict = await auth.get_credentials_dict()
                if creds_dict and creds_dict.get('access_token'):
                    print("You're now ready to upload to Facebook!")
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