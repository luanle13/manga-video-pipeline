from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Dict


class Platform(StrEnum):
    """Supported social media platforms."""
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    FACEBOOK = "facebook"


class UploadStatus(StrEnum):
    """Status of the upload."""
    PENDING = "pending"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class UploadResult:
    """Result of an upload operation."""
    platform: Platform
    video_path: Path
    upload_id: str | None
    status: UploadStatus
    details: Dict[str, Any] | None = None
    error_message: str | None = None


class BaseUploader(ABC):
    """Abstract base class for uploader implementations."""
    
    def __init__(self, credentials: Dict[str, str]):
        """
        Initialize the uploader.
        
        Args:
            credentials: Dictionary containing platform-specific credentials
        """
        self.credentials = credentials
    
    @abstractmethod
    async def upload(self, video_path: Path, title: str, description: str, 
                    tags: list[str], hashtags: list[str]) -> UploadResult:
        """
        Upload a video to the platform.
        
        Args:
            video_path: Path to the video file to upload
            title: Title of the video
            description: Description of the video
            tags: List of tags for the video
            hashtags: List of hashtags for the video
            
        Returns:
            UploadResult object with upload status and details
        """
        pass
    
    @abstractmethod
    async def check_status(self, upload_id: str) -> UploadStatus:
        """
        Check the status of an upload.
        
        Args:
            upload_id: ID of the upload to check
            
        Returns:
            Current status of the upload
        """
        pass
    
    @abstractmethod
    async def validate_credentials(self) -> bool:
        """
        Validate the provided credentials.
        
        Returns:
            True if credentials are valid, False otherwise
        """
        pass