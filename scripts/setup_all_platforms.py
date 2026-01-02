#!/usr/bin/env python3
"""
Interactive CLI script to set up authentication for all platforms.
This script sequentially runs the setup for YouTube, TikTok, and Facebook.
"""

import asyncio
import subprocess
import sys
from pathlib import Path


async def run_setup_script(script_name: str, description: str) -> bool:
    """Run a setup script and return True if successful."""
    print(f"\n{'='*50}")
    print(f"Setting up: {description}")
    print(f"{'='*50}")
    
    script_path = Path("scripts") / script_name
    if not script_path.exists():
        print(f"Error: Script {script_path} not found!")
        return False
    
    try:
        result = subprocess.run([sys.executable, str(script_path)], check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"Error running {script_name}: {e}")
        return False
    except KeyboardInterrupt:
        print(f"\nSetup for {description} interrupted by user.")
        return False


async def main():
    """Main function to run all platform setups in sequence."""
    print("=== All Platform Authentication Setup ===\n")
    print("This script will guide you through setting up authentication for all platforms:")
    print("- YouTube OAuth")
    print("- TikTok API")
    print("- Facebook API\n")
    
    print("Before starting, make sure you have:")
    print("1. YouTube Client Secrets JSON file")
    print("2. TikTok Client Key and Secret")
    print("3. Facebook App ID and Secret\n")
    
    # Confirm the user is ready
    ready = input("Are you ready to begin the setup process? (Y/n): ").strip().lower()
    if ready == 'n':
        print("Setup canceled.")
        return 0
    
    # Create credentials directory if it doesn't exist
    credentials_dir = Path("credentials")
    credentials_dir.mkdir(exist_ok=True)
    
    # Track success of each setup
    results = {
        'youtube': False,
        'tiktok': False,
        'facebook': False
    }
    
    # Run YouTube setup
    results['youtube'] = await run_setup_script(
        "setup_youtube_oauth.py",
        "YouTube OAuth"
    )
    
    print("\n" + "="*50)
    input("Press Enter to continue to the next platform setup...")
    
    # Run TikTok setup
    results['tiktok'] = await run_setup_script(
        "setup_tiktok_auth.py", 
        "TikTok API"
    )
    
    print("\n" + "="*50)
    input("Press Enter to continue to the next platform setup...")
    
    # Run Facebook setup
    results['facebook'] = await run_setup_script(
        "setup_facebook_auth.py",
        "Facebook API"
    )
    
    # Summary
    print(f"\n{'='*50}")
    print("Setup Summary:")
    print(f"{'='*50}")
    print(f"YouTube OAuth: {'✓' if results['youtube'] else '✗'}")
    print(f"TikTok API: {'✓' if results['tiktok'] else '✗'}")
    print(f"Facebook API: {'✓' if results['facebook'] else '✗'}")
    
    successful_count = sum(results.values())
    total_count = len(results)
    
    if successful_count == total_count:
        print(f"\n🎉 All platforms set up successfully! ({successful_count}/{total_count})")
        print("You're now ready to upload to all platforms!")
        return 0
    elif successful_count > 0:
        print(f"\n⚠️  Partial success! ({successful_count}/{total_count})")
        print("You can run this script again to complete any failed setups.")
        return 0
    else:
        print(f"\n❌ No platforms set up successfully. ({successful_count}/{total_count})")
        print("Please check the error messages above and try again.")
        return 1


if __name__ == "__main__":
    # Run the async main function
    sys.exit(asyncio.run(main()))