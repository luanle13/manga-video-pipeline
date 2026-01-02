from __future__ import annotations
import asyncio
import json
from pathlib import Path
from typing import Dict, Optional
import httpx
import aiofiles


class FacebookAuth:
    """Handle Facebook OAuth flow and credentials management."""
    
    def __init__(self, credentials_path: Path | str = "credentials/facebook_credentials.json"):
        """
        Initialize FacebookAuth.
        
        Args:
            credentials_path: Path to store/load credentials
        """
        self.credentials_path = Path(credentials_path)
        self.credentials_path.parent.mkdir(parents=True, exist_ok=True)
        self.credentials: Dict[str, str] = {}
    
    async def load_credentials(self) -> bool:
        """
        Load credentials from file.
        
        Returns:
            True if credentials were loaded successfully, False otherwise
        """
        if not self.credentials_path.exists():
            return False
        
        try:
            async with aiofiles.open(self.credentials_path, 'r') as f:
                creds_data = await f.read()
                self.credentials = json.loads(creds_data)
            
            return True
        except Exception as e:
            print(f"Error loading credentials: {e}")
            return False
    
    async def save_credentials(self) -> bool:
        """
        Save current credentials to file.
        
        Returns:
            True if credentials were saved successfully, False otherwise
        """
        try:
            async with aiofiles.open(self.credentials_path, 'w') as f:
                await f.write(json.dumps(self.credentials, indent=2))
            
            return True
        except Exception as e:
            print(f"Error saving credentials: {e}")
            return False
    
    async def refresh_access_token(self) -> bool:
        """
        Refresh the access token if it's expired.
        
        Returns:
            True if token was refreshed or was already valid, False otherwise
        """
        if not self.credentials.get('app_access_token'):
            return False
        
        try:
            # Facebook long-lived tokens don't typically need refreshing the same way,
            # but we can extend the life of user access tokens
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://graph.facebook.com/v18.0/oauth/access_token",
                    params={
                        'grant_type': 'fb_exchange_token',
                        'client_id': self.credentials.get('app_id', ''),
                        'client_secret': self.credentials.get('app_secret', ''),
                        'fb_exchange_token': self.credentials.get('access_token', '')
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if 'access_token' in data:
                        # Update access token with extended one
                        self.credentials['access_token'] = data['access_token']
                        self.credentials['expires_in'] = data.get('expires_in', 0)
                        
                        # Save updated credentials
                        await self.save_credentials()
                        return True
            
            return False
        except Exception as e:
            print(f"Error refreshing access token: {e}")
            return False
    
    async def is_token_valid(self) -> bool:
        """
        Check if the current token is valid by making a simple API call.
        
        Returns:
            True if token is valid, False otherwise
        """
        if not self.credentials.get('access_token'):
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://graph.facebook.com/v18.0/me/accounts",
                    params={
                        'access_token': self.credentials['access_token'],
                        'fields': 'id,name'
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return 'data' in data
                
        except Exception:
            pass
        
        return False
    
    async def authenticate(self, app_id: str, app_secret: str, redirect_uri: str) -> bool:
        """
        Perform OAuth flow to get credentials.
        
        Args:
            app_id: Facebook app ID
            app_secret: Facebook app secret
            redirect_uri: Redirect URI for OAuth flow
            
        Returns:
            True if authentication was successful, False otherwise
        """
        try:
            # Store app credentials
            self.credentials['app_id'] = app_id
            self.credentials['app_secret'] = app_secret
            
            print("Facebook OAuth setup instructions:")
            print(f"1. Go to: https://developers.facebook.com/apps/{app_id}/settings/")
            print(f"2. Set your redirect URI to: {redirect_uri}")
            print("3. After setting up, you'll need to generate a long-lived access token")
            print("4. First, get a short-lived access token from Facebook Developers page")
            print("5. Then, exchange it for a long-lived token")
            print("6. Enter your short-lived access token below (or long-lived if you already have one):")
            
            short_lived_token = input("Access token: ").strip()
            
            if not short_lived_token:
                print("No access token provided.")
                return False
            
            # Get long-lived access token
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://graph.facebook.com/v18.0/oauth/access_token",
                    params={
                        'grant_type': 'fb_exchange_token',
                        'client_id': app_id,
                        'client_secret': app_secret,
                        'fb_exchange_token': short_lived_token
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if 'access_token' in data:
                        # Store the long-lived token
                        self.credentials['access_token'] = data['access_token']
                        self.credentials['expires_in'] = data.get('expires_in', 0)
                        
                        # Now get page access tokens for all pages the user manages
                        page_response = await client.get(
                            f"https://graph.facebook.com/v18.0/me/accounts",
                            params={
                                'access_token': self.credentials['access_token'],
                                'fields': 'id,name,access_token'
                            }
                        )
                        
                        if page_response.status_code == 200:
                            page_data = page_response.json()
                            if 'data' in page_data and page_data['data']:
                                print("\nAvailable pages:")
                                for i, page in enumerate(page_data['data']):
                                    print(f"{i + 1}. {page['name']} (ID: {page['id']})")
                                
                                # Let user select a page
                                while True:
                                    try:
                                        choice = int(input("Select a page to use (enter number): ")) - 1
                                        if 0 <= choice < len(page_data['data']):
                                            selected_page = page_data['data'][choice]
                                            self.credentials['page_id'] = selected_page['id']
                                            self.credentials['page_access_token'] = selected_page['access_token']
                                            break
                                        else:
                                            print("Invalid selection. Please try again.")
                                    except ValueError:
                                        print("Please enter a valid number.")
                        
                        # Save credentials
                        return await self.save_credentials()
                    else:
                        print(f"Error getting long-lived access token: {data}")
                        return False
                else:
                    print(f"HTTP error: {response.status_code}")
                    return False
            
        except Exception as e:
            print(f"Authentication failed: {e}")
            return False
    
    async def get_credentials_dict(self) -> Dict[str, str] | None:
        """
        Get credentials as a dictionary suitable for uploader modules.
        
        Returns:
            Dictionary with credential information or None if not available
        """
        if not await self.is_token_valid():
            return None
        
        return {
            'access_token': self.credentials.get('page_access_token', self.credentials.get('access_token', '')),
            'page_id': self.credentials.get('page_id', ''),
            'app_id': self.credentials.get('app_id', ''),
            'app_secret': self.credentials.get('app_secret', '')
        }


# Convenience function for English Facebook account/page
async def authenticate_facebook_en(app_id: str, app_secret: str, redirect_uri: str) -> Dict[str, str] | None:
    """Authenticate Facebook account/page for English content."""
    auth = FacebookAuth("credentials/facebook_en_credentials.json")
    if await auth.load_credentials():
        if await auth.is_token_valid():
            return await auth.get_credentials_dict()
    
    # If no valid credentials, perform authentication
    success = await auth.authenticate(app_id, app_secret, redirect_uri)
    if success:
        return await auth.get_credentials_dict()
    
    return None


# Convenience function for Vietnamese Facebook account/page
async def authenticate_facebook_vn(app_id: str, app_secret: str, redirect_uri: str) -> Dict[str, str] | None:
    """Authenticate Facebook account/page for Vietnamese content."""
    auth = FacebookAuth("credentials/facebook_vn_credentials.json")
    if await auth.load_credentials():
        if await auth.is_token_valid():
            return await auth.get_credentials_dict()
    
    # If no valid credentials, perform authentication
    success = await auth.authenticate(app_id, app_secret, redirect_uri)
    if success:
        return await auth.get_credentials_dict()
    
    return None