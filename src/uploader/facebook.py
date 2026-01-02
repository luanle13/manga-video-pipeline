from __future__ import annotations
import asyncio
from pathlib import Path
from typing import Dict, List
import httpx
import time

from .base import BaseUploader, Platform, UploadResult, UploadStatus


class FacebookUploader(BaseUploader):
    """Uploader for Facebook using Meta Graph API."""
    
    def __init__(self, credentials: Dict[str, str]):
        """
        Initialize the Facebook uploader.
        
        Args:
            credentials: Dictionary containing Facebook API credentials
                        Expected keys: 'access_token', 'page_id'
        """
        super().__init__(credentials)
        self.access_token = credentials.get('access_token', '')
        self.page_id = credentials.get('page_id', '')
        self.base_url = "https://graph.facebook.com/v18.0"
    
    async def upload(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: List[str],
        hashtags: List[str]
    ) -> UploadResult:
        """
        Upload a video to Facebook as a Reel.
        
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
            async with httpx.AsyncClient() as client:
                # First step: Initiate the upload
                init_response = await client.post(
                    f"{self.base_url}/{self.page_id}/videos",
                    data={
                        'access_token': self.access_token,
                        'upload_phase': 'start',
                        'title': title,
                        'description': description,
                        'has.instagram_story': 'false',  # This is for regular video, not story
                        # For Facebook Reels, we need to specify this is for Instagram Reels
                        # which will also appear on Facebook Reels
                    }
                )
                
                if init_response.status_code != 200:
                    raise Exception(f"Failed to initiate Facebook upload: {init_response.text}")
                
                init_data = init_response.json()
                upload_id = init_data.get('upload_id')
                
                if not upload_id:
                    raise Exception("Failed to get upload_id from Facebook API")
                
                # Second step: Upload the video file in chunks
                file_size = video_path.stat().st_size
                chunk_size = 1024 * 1024 * 4  # 4MB chunks
                
                with open(video_path, 'rb') as video_file:
                    start_offset = 0
                    while start_offset < file_size:
                        end_offset = min(start_offset + chunk_size, file_size)
                        chunk = video_file.read(chunk_size)
                        
                        # Upload the chunk
                        chunk_response = await client.post(
                            f"{self.base_url}/{self.page_id}/videos",
                            data={
                                'access_token': self.access_token,
                                'upload_phase': 'transfer',
                                'upload_id': upload_id,
                                'start_offset': str(start_offset),
                                'end_offset': str(end_offset),
                            },
                            files={
                                'video_file_chunk': (video_path.name, chunk, 'video/mp4')
                            }
                        )
                        
                        if chunk_response.status_code != 200:
                            raise Exception(f"Failed to upload chunk: {chunk_response.text}")
                        
                        start_offset = end_offset
                
                # Third step: Finalize the upload
                finalize_response = await client.post(
                    f"{self.base_url}/{self.page_id}/videos",
                    data={
                        'access_token': self.access_token,
                        'upload_phase': 'finish',
                        'upload_id': upload_id,
                        'title': title,
                        'description': description,
                        'is_instagram_eligible': 'true',
                        'video_state': 'PUBLISHED',  # Set video as published
                        'container_type': 'REELS'  # Specify this is for Reels
                    }
                )
                
                if finalize_response.status_code != 200:
                    raise Exception(f"Failed to finalize Facebook upload: {finalize_response.text}")
                
                finalize_data = finalize_response.json()
                video_id = finalize_data.get('id')
                
                if not video_id:
                    raise Exception("Failed to get video_id after finalizing upload")
                
                return UploadResult(
                    platform=Platform.FACEBOOK,
                    video_path=video_path,
                    upload_id=video_id,
                    status=UploadStatus.COMPLETED,
                    details={
                        "url": f"https://www.facebook.com/{self.page_id}/videos/{video_id}",
                        "title": title,
                        "description": description,
                        "tags": tags,
                        "hashtags": hashtags
                    }
                )
                
        except Exception as e:
            return UploadResult(
                platform=Platform.FACEBOOK,
                video_path=video_path,
                upload_id=None,
                status=UploadStatus.FAILED,
                error_message=str(e)
            )
    
    async def check_status(self, upload_id: str) -> UploadStatus:
        """
        Check the status of a Facebook upload.
        
        Args:
            upload_id: ID of the upload to check
            
        Returns:
            Current status of the upload
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/{upload_id}",
                    params={
                        'access_token': self.access_token,
                        'fields': 'status'
                    }
                )
                
                if response.status_code != 200:
                    return UploadStatus.FAILED
                
                data = response.json()
                if 'error' in data:
                    return UploadStatus.FAILED
                
                # Check video status
                status_info = data.get('status', {})
                upload_status = status_info.get('upload_status', 'processing')
                
                if upload_status == 'complete':
                    return UploadStatus.COMPLETED
                elif upload_status in ['failed', 'error']:
                    return UploadStatus.FAILED
                else:
                    # This could be 'processing', 'uploaded', etc.
                    return UploadStatus.UPLOADING
                    
        except Exception:
            return UploadStatus.FAILED
    
    async def validate_credentials(self) -> bool:
        """
        Validate the Facebook API credentials.
        
        Returns:
            True if credentials are valid, False otherwise
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/me/accounts",
                    params={
                        'access_token': self.access_token
                    }
                )
                
                if response.status_code != 200:
                    return False
                
                data = response.json()
                return 'data' in data  # If we get account data, credentials are valid
                
        except Exception:
            return False