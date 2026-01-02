from __future__ import annotations
import asyncio
import json
import os
from pathlib import Path
from typing import Dict, Optional
import google.auth.transport.requests
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import aiofiles


class YouTubeAuth:
    """Handle YouTube OAuth flow and credentials management."""
    
    SCOPES = [
        'https://www.googleapis.com/auth/youtube.upload',
        'https://www.googleapis.com/auth/youtube',
        'https://www.googleapis.com/auth/youtube.readonly'
    ]
    
    def __init__(self, credentials_path: Path | str = "credentials/youtube_credentials.json"):
        """
        Initialize YouTubeAuth.
        
        Args:
            credentials_path: Path to store/load credentials
        """
        self.credentials_path = Path(credentials_path)
        self.credentials_path.parent.mkdir(parents=True, exist_ok=True)
        self.credentials: Optional[Credentials] = None
    
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
                creds_json = json.loads(creds_data)
            
            self.credentials = Credentials.from_authorized_user_info(creds_json)
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
            if not self.credentials:
                return False
            
            creds_data = self.credentials.to_json()
            
            async with aiofiles.open(self.credentials_path, 'w') as f:
                await f.write(creds_data)
            
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
        if not self.credentials:
            return False
        
        try:
            if self.credentials.expired and self.credentials.refresh_token:
                # Refresh the token asynchronously by running the sync operation in a thread
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: self.credentials.refresh(Request()))
                
                # Save the refreshed credentials
                await self.save_credentials()
                return True
            elif not self.credentials.expired:
                return True
            else:
                return False
        except RefreshError:
            # Token refresh failed, need to re-authenticate
            print("Access token refresh failed. Please re-authenticate.")
            return False
    
    async def is_token_valid(self) -> bool:
        """
        Check if the current token is valid and not expired.
        
        Returns:
            True if token is valid, False otherwise
        """
        if not self.credentials:
            return False
        
        # Try to refresh if expired
        return await self.refresh_access_token()
    
    async def authenticate(self, client_secrets_path: Path | str) -> bool:
        """
        Perform OAuth flow to get credentials.
        
        Args:
            client_secrets_path: Path to client secrets JSON file
            
        Returns:
            True if authentication was successful, False otherwise
        """
        try:
            # Load client secrets
            async with aiofiles.open(client_secrets_path, 'r') as f:
                client_config = json.loads(await f.read())
            
            # Create flow
            flow = InstalledAppFlow.from_client_config(
                client_config, 
                self.SCOPES
            )
            
            # Run flow using local server
            loop = asyncio.get_event_loop()
            self.credentials = await loop.run_in_executor(
                None, 
                lambda: flow.run_local_server(port=0)
            )
            
            # Save credentials
            return await self.save_credentials()
            
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
            'client_id': self.credentials.client_id if self.credentials else '',
            'client_secret': self.credentials.client_secret if self.credentials else '',
            'refresh_token': self.credentials.refresh_token if self.credentials else '',
            'access_token': self.credentials.token if self.credentials else ''
        }


# Convenience function for English YouTube account
async def authenticate_youtube_en(client_secrets_path: Path | str) -> Dict[str, str] | None:
    """Authenticate YouTube account for English content."""
    auth = YouTubeAuth("credentials/youtube_en_credentials.json")
    if await auth.load_credentials():
        if await auth.is_token_valid():
            return await auth.get_credentials_dict()
    
    # If no valid credentials, perform authentication
    success = await auth.authenticate(client_secrets_path)
    if success:
        return await auth.get_credentials_dict()
    
    return None


# Convenience function for Vietnamese YouTube account
async def authenticate_youtube_vn(client_secrets_path: Path | str) -> Dict[str, str] | None:
    """Authenticate YouTube account for Vietnamese content."""
    auth = YouTubeAuth("credentials/youtube_vn_credentials.json")
    if await auth.load_credentials():
        if await auth.is_token_valid():
            return await auth.get_credentials_dict()
    
    # If no valid credentials, perform authentication
    success = await auth.authenticate(client_secrets_path)
    if success:
        return await auth.get_credentials_dict()
    
    return None