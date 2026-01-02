from __future__ import annotations
import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError

from .base import BaseUploader, Platform, UploadResult, UploadStatus


class YouTubeUploader(BaseUploader):
    """Uploader for YouTube using YouTube Data API v3."""
    
    def __init__(self, credentials: Dict[str, str]):
        """
        Initialize the YouTube uploader.
        
        Args:
            credentials: Dictionary containing YouTube API credentials
                        Expected keys: 'client_id', 'client_secret', 'refresh_token', 'access_token'
        """
        super().__init__(credentials)
        self.api_service = None
        self._credentials = None
    
    async def _setup_api_service(self) -> None:
        """Set up the YouTube API service."""
        # This would handle OAuth 2.0 authentication using the provided credentials
        try:
            # Create credentials object from the provided data
            token_data = {
                "token": self.credentials.get('access_token', ''),
                "refresh_token": self.credentials.get('refresh_token', ''),
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": self.credentials.get('client_id', ''),
                "client_secret": self.credentials.get('client_secret', ''),
            }
            
            self._credentials = Credentials(token=None, **token_data)
            
            # Build the service
            self.api_service = build('youtube', 'v3', credentials=self._credentials)
        except Exception as e:
            raise Exception(f"Failed to set up YouTube API service: {str(e)}")
    
    async def upload(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: List[str],
        hashtags: List[str]
    ) -> UploadResult:
        """
        Upload a video to YouTube as a Short.
        
        Args:
            video_path: Path to the video file to upload
            title: Title of the video
            description: Description of the video
            tags: List of tags for the video
            hashtags: List of hashtags for the video
            
        Returns:
            UploadResult object with upload status and details
        """
        try:
            if not self.api_service:
                await self._setup_api_service()
            
            # Combine tags and hashtags
            all_tags = tags + [tag.lstrip('#') for tag in hashtags if tag.startswith('#')]
            
            # Prepare metadata
            body = {
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": all_tags,
                    "categoryId": "24"  # People & Blogs category
                },
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": False,
                },
                "recordingDetails": {
                    # Indicate that this is a Short
                    "recordingDate": None  # This should be set to actual date
                }
            }
            
            # Add video as YouTube Short by setting the appropriate parameter
            media_body = MediaFileUpload(str(video_path), mimetype='video/mp4', resumable=True)
            
            # Perform upload
            request = self.api_service.videos().insert(
                part="snippet,status,recordingDetails",
                body=body,
                media_body=media_body
            )
            
            response = None
            error = None
            retry = 0
            max_retries = 3
            
            while response is None:
                try:
                    print(f"Uploading to YouTube: {retry + 1}/{max_retries}")
                    status, response = request.next_chunk()
                    if status:
                        print(f"Uploaded {int(status.progress() * 100)}%.")
                except Exception as e:
                    error = e
                    retry += 1
                    if retry >= max_retries:
                        break
                    await asyncio.sleep(2 ** retry)  # Exponential backoff
            
            if response:
                video_id = response.get('id')
                url = f"https://www.youtube.com/watch?v={video_id}"
                
                return UploadResult(
                    platform=Platform.YOUTUBE,
                    video_path=video_path,
                    upload_id=video_id,
                    status=UploadStatus.COMPLETED,
                    details={
                        "url": url,
                        "title": title,
                        "description": description,
                        "tags": all_tags
                    }
                )
            else:
                raise Exception(f"Upload failed after {max_retries} retries: {error}")
                
        except Exception as e:
            return UploadResult(
                platform=Platform.YOUTUBE,
                video_path=video_path,
                upload_id=None,
                status=UploadStatus.FAILED,
                error_message=str(e)
            )
    
    async def check_status(self, upload_id: str) -> UploadStatus:
        """
        Check the status of a YouTube upload.
        
        Args:
            upload_id: ID of the upload to check
            
        Returns:
            Current status of the upload
        """
        try:
            if not self.api_service:
                await self._setup_api_service()
            
            # Retrieve video status
            response = self.api_service.videos().list(
                id=upload_id,
                part="status"
            ).execute()
            
            if not response.get("items"):
                return UploadStatus.FAILED
            
            video_status = response["items"][0]["status"]["uploadStatus"]
            
            if video_status == "processed":
                return UploadStatus.COMPLETED
            elif video_status in ["failed", "rejected"]:
                return UploadStatus.FAILED
            else:
                return UploadStatus.UPLOADING
                
        except Exception:
            return UploadStatus.FAILED
    
    async def validate_credentials(self) -> bool:
        """
        Validate the YouTube API credentials.
        
        Returns:
            True if credentials are valid, False otherwise
        """
        try:
            if not self.api_service:
                await self._setup_api_service()
            
            # Try to fetch channels to validate credentials
            response = self.api_service.channels().list(
                part="snippet",
                mine=True
            ).execute()
            
            # If we get a response without error, credentials are valid
            return "items" in response
            
        except Exception:
            return False