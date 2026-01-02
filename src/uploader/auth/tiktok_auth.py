from __future__ import annotations
import asyncio
import json
from pathlib import Path
from typing import Dict, Optional
import httpx
import aiofiles


class TikTokAuth:
    """Handle TikTok OAuth flow and credentials management."""
    
    def __init__(self, credentials_path: Path | str = "credentials/tiktok_credentials.json"):
        """
        Initialize TikTokAuth.
        
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
        if not self.credentials.get('refresh_token') or not self.credentials.get('client_key') or not self.credentials.get('client_secret'):
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://open-api.tiktok.com/oauth/refresh_token",
                    params={
                        'client_key': self.credentials['client_key'],
                        'client_secret': self.credentials['client_secret'],
                        'grant_type': 'refresh_token',
                        'refresh_token': self.credentials['refresh_token']
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('error_code') == 0:
                        # Update credentials with new access token
                        self.credentials['access_token'] = data.get('data', {}).get('access_token', '')
                        self.credentials['refresh_token'] = data.get('data', {}).get('refresh_token', '')
                        
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
                    "https://open-api.tiktok.com/oauth/inspect_token",
                    params={
                        'access_token': self.credentials['access_token']
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get('error_code') == 0
                
        except Exception:
            pass
        
        # If the token is invalid, try to refresh it
        return await self.refresh_access_token()
    
    async def authenticate(self, client_key: str, client_secret: str, redirect_uri: str, scopes: list[str] = None) -> bool:
        """
        Perform OAuth flow to get credentials.
        
        Args:
            client_key: TikTok app client key
            client_secret: TikTok app client secret
            redirect_uri: Redirect URI for OAuth flow
            scopes: List of permissions to request
            
        Returns:
            True if authentication was successful, False otherwise
        """
        try:
            # Store app credentials
            self.credentials['client_key'] = client_key
            self.credentials['client_secret'] = client_secret
            
            # For TikTok, the OAuth flow typically involves:
            # 1. Redirecting user to TikTok authorization URL
            # 2. User grants permission
            # 3. TikTok redirects back with authorization code
            # 4. Exchange code for access token
            
            print("TikTok OAuth setup instructions:")
            print(f"1. Go to: https://developers.tiktok.com/doc/oauth-user-authorization-flow")
            print(f"2. Set your redirect URI to: {redirect_uri}")
            print(f"3. Use client_key: {client_key}")
            print("4. After authorization, you'll receive an authorization code")
            print("5. Enter the authorization code below:")
            
            auth_code = input("Authorization code: ").strip()
            
            if not auth_code:
                print("No authorization code provided.")
                return False
            
            # Exchange authorization code for access token
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://open-api.tiktok.com/oauth/access_token/",
                    params={
                        'client_key': client_key,
                        'client_secret': client_secret,
                        'code': auth_code,
                        'grant_type': 'authorization_code',
                        'redirect_uri': redirect_uri
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('error_code') == 0:
                        token_data = data.get('data', {})
                        self.credentials['access_token'] = token_data.get('access_token', '')
                        self.credentials['refresh_token'] = token_data.get('refresh_token', '')
                        self.credentials['open_id'] = token_data.get('open_id', '')
                        
                        # Save credentials
                        return await self.save_credentials()
                    else:
                        print(f"Error getting access token: {data.get('description', 'Unknown error')}")
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
            'access_token': self.credentials.get('access_token', ''),
            'client_key': self.credentials.get('client_key', ''),
            'client_secret': self.credentials.get('client_secret', '')
        }


# Convenience function for English TikTok account
async def authenticate_tiktok_en(client_key: str, client_secret: str, redirect_uri: str) -> Dict[str, str] | None:
    """Authenticate TikTok account for English content."""
    auth = TikTokAuth("credentials/tiktok_en_credentials.json")
    if await auth.load_credentials():
        if await auth.is_token_valid():
            return await auth.get_credentials_dict()
    
    # If no valid credentials, perform authentication
    success = await auth.authenticate(client_key, client_secret, redirect_uri)
    if success:
        return await auth.get_credentials_dict()
    
    return None


# Convenience function for Vietnamese TikTok account
async def authenticate_tiktok_vn(client_key: str, client_secret: str, redirect_uri: str) -> Dict[str, str] | None:
    """Authenticate TikTok account for Vietnamese content."""
    auth = TikTokAuth("credentials/tiktok_vn_credentials.json")
    if await auth.load_credentials():
        if await auth.is_token_valid():
            return await auth.get_credentials_dict()
    
    # If no valid credentials, perform authentication
    success = await auth.authenticate(client_key, client_secret, redirect_uri)
    if success:
        return await auth.get_credentials_dict()
    
    return None