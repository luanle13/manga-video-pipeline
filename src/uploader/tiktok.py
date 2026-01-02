from __future__ import annotations
import asyncio
from pathlib import Path
from typing import Dict, List
import httpx
import json
import time

from .base import BaseUploader, Platform, UploadResult, UploadStatus


class TikTokUploader(BaseUploader):
    """Uploader for TikTok using TikTok Content Posting API."""
    
    def __init__(self, credentials: Dict[str, str]):
        """
        Initialize the TikTok uploader.
        
        Args:
            credentials: Dictionary containing TikTok API credentials
                        Expected keys: 'access_token', 'client_key', 'client_secret'
        """
        super().__init__(credentials)
        self.access_token = credentials.get('access_token', '')
        self.client_key = credentials.get('client_key', '')
        self.client_secret = credentials.get('client_secret', '')
        self.base_url = "https://open-api.tiktok.com"
    
    async def upload(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: List[str],
        hashtags: List[str]
    ) -> UploadResult:
        """
        Upload a video to TikTok with caption and hashtags.
        
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
            # Combine title with hashtags for caption
            caption = title
            if hashtags:
                caption += " " + " ".join(hashtags[:10])  # TikTok has hashtag limits
            
            # First, upload the video file to TikTok
            async with httpx.AsyncClient() as client:
                # Upload the video file
                with open(video_path, 'rb') as video_file:
                    files = {
                        'video': (video_path.name, video_file, 'video/mp4')
                    }
                    
                    upload_response = await client.post(
                        f"{self.base_url}/video/upload/init",
                        params={
                            'access_token': self.access_token
                        },
                        files=files
                    )
                
                if upload_response.status_code != 200:
                    raise Exception(f"Failed to upload video: {upload_response.text}")
                
                upload_data = upload_response.json()
                if upload_data.get('error_code') != 0:
                    raise Exception(f"TikTok API error: {upload_data.get('description', 'Unknown error')}")
                
                # Get the upload_id for the publish step
                upload_id = upload_data.get('data', {}).get('upload_id')
                
                # Publish the video with caption
                publish_data = {
                    'access_token': self.access_token,
                    'post_info': json.dumps({
                        'title': title,
                        'description': description,
                        'upload_id': upload_id,
                        'privacy_level': 'PUBLIC',  # PUBLIC, FRIENDS, or PRIVATE
                        'comment_disabled': 0,  # 0 to enable comments, 1 to disable
                        'download_disabled': 0,  # 0 to enable download, 1 to disable
                        'caption': caption,
                        'disable_pc_share': 0
                    })
                }
                
                publish_response = await client.post(
                    f"{self.base_url}/video/publish",
                    data=publish_data
                )
                
                if publish_response.status_code != 200:
                    raise Exception(f"Failed to publish video: {publish_response.text}")
                
                publish_data = publish_response.json()
                if publish_data.get('error_code') != 0:
                    raise Exception(f"TikTok publish API error: {publish_data.get('description', 'Unknown error')}")
                
                # Check the publishing status
                publish_id = publish_data.get('data', {}).get('publish_id')
                
                # Return successful result
                return UploadResult(
                    platform=Platform.TIKTOK,
                    video_path=video_path,
                    upload_id=publish_id,
                    status=UploadStatus.COMPLETED,
                    details={
                        "caption": caption,
                        "title": title,
                        "description": description,
                        "tags": tags,
                        "hashtags": hashtags
                    }
                )
                
        except Exception as e:
            return UploadResult(
                platform=Platform.TIKTOK,
                video_path=video_path,
                upload_id=None,
                status=UploadStatus.FAILED,
                error_message=str(e)
            )
    
    async def check_status(self, upload_id: str) -> UploadStatus:
        """
        Check the status of a TikTok upload.
        
        Args:
            upload_id: ID of the upload to check
            
        Returns:
            Current status of the upload
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/video/query/",
                    params={
                        'access_token': self.access_token,
                        'publish_id': upload_id
                    }
                )
                
                if response.status_code != 200:
                    return UploadStatus.FAILED
                
                data = response.json()
                if data.get('error_code') != 0:
                    return UploadStatus.FAILED
                
                # Check publish state
                publish_state = data.get('data', {}).get('state', 0)
                
                # State codes: 0=Processing, 1=Success, 2=Failed, 3=Not Found
                if publish_state == 1:
                    return UploadStatus.COMPLETED
                elif publish_state == 2:
                    return UploadStatus.FAILED
                elif publish_state == 3:
                    return UploadStatus.FAILED
                else:
                    return UploadStatus.UPLOADING
                    
        except Exception:
            return UploadStatus.FAILED
    
    async def validate_credentials(self) -> bool:
        """
        Validate the TikTok API credentials.
        
        Returns:
            True if credentials are valid, False otherwise
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/user/info/",
                    params={
                        'access_token': self.access_token,
                        'fields': 'open_id,display_name,avatar'
                    }
                )
                
                if response.status_code != 200:
                    return False
                
                data = response.json()
                return data.get('error_code') == 0
                
        except Exception:
            return False