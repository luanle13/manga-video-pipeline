import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
from dataclasses import dataclass
import tempfile


@dataclass
class MockUploadResult:
    """Mock class for UploadResult."""
    platform: str
    video_path: Path
    upload_id: str
    status: str
    details: dict = None
    error_message: str = None


@dataclass
class MockUploadManagerConfig:
    """Mock class for UploadManagerConfig."""
    youtube_credentials: dict = None
    tiktok_credentials: dict = None
    facebook_credentials: dict = None


class TestUploadManager:
    """Test cases for the Upload Manager."""
    
    @pytest.mark.asyncio
    async def test_upload_to_all_platforms_happy_path(self):
        """Test the upload_to_all_platforms function with valid inputs."""
        from src.uploader.manager import UploadManager, UploadManagerConfig
        from src.uploader.base import Platform
        
        mock_config = MockUploadManagerConfig(
            youtube_credentials={'access_token': 'youtube_token'},
            tiktok_credentials={'access_token': 'tiktok_token'},
            facebook_credentials={'access_token': 'facebook_token'}
        )
        
        # Create a mock UploadManager that doesn't actually call real APIs
        with patch('src.uploader.youtube.YouTubeUploader') as mock_youtube, \
             patch('src.uploader.tiktok.TikTokUploader') as mock_tiktok, \
             patch('src.uploader.facebook.FacebookUploader') as mock_fb:
            
            # Mock YouTube uploader
            mock_yt_instance = AsyncMock()
            mock_yt_instance.upload.return_value = MockUploadResult(
                platform=Platform.YOUTUBE,
                video_path=Path("test.mp4"),
                upload_id="yt_test_id",
                status="completed"
            )
            mock_youtube.return_value = mock_yt_instance
            
            # Mock TikTok uploader
            mock_tt_instance = AsyncMock()
            mock_tt_instance.upload.return_value = MockUploadResult(
                platform=Platform.TIKTOK,
                video_path=Path("test.mp4"),
                upload_id="tt_test_id",
                status="completed"
            )
            mock_tiktok.return_value = mock_tt_instance
            
            # Mock Facebook uploader
            mock_fb_instance = AsyncMock()
            mock_fb_instance.upload.return_value = MockUploadResult(
                platform=Platform.FACEBOOK,
                video_path=Path("test.mp4"),
                upload_id="fb_test_id",
                status="completed"
            )
            mock_fb.return_value = mock_fb_instance
            
            upload_manager = UploadManager(mock_config)
            
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                video_path = Path(temp_file.name)
            
            try:
                results = await upload_manager.upload_to_all_platforms(
                    video_path=video_path,
                    title="Test Video",
                    description="Test Description",
                    tags=["test", "manga"],
                    hashtags=["#test", "#manga"],
                    languages={Platform.YOUTUBE: "en", Platform.TIKTOK: "en", Platform.FACEBOOK: "en"}
                )
                
                assert len(results) == 3
                assert all(result.status == "completed" for result in results)
                assert any(result.platform == Platform.YOUTUBE for result in results)
                assert any(result.platform == Platform.TIKTOK for result in results)
                assert any(result.platform == Platform.FACEBOOK for result in results)
                
                # Verify that all uploaders were called
                mock_yt_instance.upload.assert_called_once()
                mock_tt_instance.upload.assert_called_once()
                mock_fb_instance.upload.assert_called_once()
                
            finally:
                # Clean up
                if video_path.exists():
                    video_path.unlink()
    
    @pytest.mark.asyncio
    async def test_upload_to_all_platforms_with_some_failures(self):
        """Test upload with mixed success/failure results."""
        from src.uploader.manager import UploadManager, UploadManagerConfig
        from src.uploader.base import Platform
        
        mock_config = MockUploadManagerConfig(
            youtube_credentials={'access_token': 'youtube_token'},
            tiktok_credentials={'access_token': 'tiktok_token'},
            facebook_credentials={'access_token': 'facebook_token'}
        )
        
        with patch('src.uploader.youtube.YouTubeUploader') as mock_youtube, \
             patch('src.uploader.tiktok.TikTokUploader') as mock_tiktok, \
             patch('src.uploader.facebook.FacebookUploader') as mock_fb:
            
            # Mock YouTube uploader to fail
            mock_yt_instance = AsyncMock()
            mock_yt_instance.upload.side_effect = Exception("YouTube upload failed")
            mock_youtube.return_value = mock_yt_instance
            
            # Mock TikTok uploader to succeed
            mock_tt_instance = AsyncMock()
            mock_tt_instance.upload.return_value = MockUploadResult(
                platform=Platform.TIKTOK,
                video_path=Path("test.mp4"),
                upload_id="tt_test_id",
                status="completed"
            )
            mock_tiktok.return_value = mock_tt_instance
            
            # Mock Facebook uploader to succeed
            mock_fb_instance = AsyncMock()
            mock_fb_instance.upload.return_value = MockUploadResult(
                platform=Platform.FACEBOOK,
                video_path=Path("test.mp4"),
                upload_id="fb_test_id",
                status="completed"
            )
            mock_fb.return_value = mock_fb_instance
            
            upload_manager = UploadManager(mock_config)
            
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                video_path = Path(temp_file.name)
            
            try:
                results = await upload_manager.upload_to_all_platforms(
                    video_path=video_path,
                    title="Test Video",
                    description="Test Description",
                    tags=["test", "manga"],
                    hashtags=["#test", "#manga"],
                    languages={Platform.YOUTUBE: "en", Platform.TIKTOK: "en", Platform.FACEBOOK: "en"}
                )
                
                # Should return 2 successful results despite YouTube failure
                assert len(results) == 2
                platforms_uploaded = [result.platform for result in results]
                assert Platform.TIKTOK in platforms_uploaded
                assert Platform.FACEBOOK in platforms_uploaded
                # YouTube should not be in results due to exception
                
            finally:
                # Clean up
                if video_path.exists():
                    video_path.unlink()
    
    @pytest.mark.asyncio
    async def test_upload_to_all_platforms_with_no_credentials(self):
        """Test upload when no credentials are provided."""
        from src.uploader.manager import UploadManager, UploadManagerConfig
        
        # No credentials provided
        mock_config = MockUploadManagerConfig()
        
        upload_manager = UploadManager(mock_config)
        
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            video_path = Path(temp_file.name)
        
        try:
            with pytest.raises(ValueError, match="No uploaders available"):
                await upload_manager.upload_to_all_platforms(
                    video_path=video_path,
                    title="Test Video",
                    description="Test Description",
                    tags=["test", "manga"],
                    hashtags=["#test", "#manga"],
                    languages={}
                )
        finally:
            # Clean up
            if video_path.exists():
                video_path.unlink()
    
    @pytest.mark.asyncio
    async def test_retry_failed_uploads_happy_path(self):
        """Test retrying failed uploads successfully."""
        from src.uploader.manager import UploadManager, UploadManagerConfig
        from src.uploader.base import Platform, UploadResult, UploadStatus
        
        mock_config = MockUploadManagerConfig(
            youtube_credentials={'access_token': 'youtube_token'},
            tiktok_credentials={'access_token': 'tiktok_token'},
            facebook_credentials={'access_token': 'facebook_token'}
        )
        
        with patch('src.uploader.youtube.YouTubeUploader') as mock_youtube, \
             patch('src.uploader.tiktok.TikTokUploader') as mock_tiktok, \
             patch('src.uploader.facebook.FacebookUploader') as mock_fb:
            
            # Mock uploaders to behave differently for retry attempts
            mock_yt_instance = AsyncMock()
            # First call fails, second succeeds
            mock_yt_instance.upload = AsyncMock(side_effect=[
                MockUploadResult(
                    platform=Platform.YOUTUBE,
                    video_path=Path("test.mp4"),
                    upload_id=None,
                    status="failed",
                    error_message="Initial failure"
                ),
                MockUploadResult(
                    platform=Platform.YOUTUBE,
                    video_path=Path("test.mp4"),
                    upload_id="yt_retry_id",
                    status="completed"
                )
            ])
            mock_youtube.return_value = mock_yt_instance
            
            upload_manager = UploadManager(mock_config)
            
            failed_result = UploadResult(
                platform=Platform.YOUTUBE,
                video_path=Path("test.mp4"),
                upload_id=None,
                status="failed",
                details={'title': 'Failed Upload', 'description': 'Test', 'tags': [], 'hashtags': []},
                error_message="Initial failure"
            )
            
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                video_path = Path(temp_file.name)
            
            try:
                # Simulate a retry
                results = await upload_manager.retry_failed_uploads([failed_result])
                
                # Should have one successful result after retry
                assert len(results) == 1
                assert results[0].status == "completed"
                assert results[0].platform == Platform.YOUTUBE
                # Verify upload was called twice (initial + retry)
                assert mock_yt_instance.upload.call_count == 2
                
            finally:
                # Clean up
                if video_path.exists():
                    video_path.unlink()
    
    @pytest.mark.asyncio
    async def test_retry_failed_uploads_still_fails(self):
        """Test retrying failed uploads that still fail."""
        from src.uploader.manager import UploadManager, UploadManagerConfig
        from src.uploader.base import Platform, UploadResult, UploadStatus
        
        mock_config = MockUploadManagerConfig(
            youtube_credentials={'access_token': 'youtube_token'}
        )
        
        with patch('src.uploader.youtube.YouTubeUploader') as mock_youtube:
            mock_yt_instance = AsyncMock()
            # Fail both initial and retry attempts
            mock_yt_instance.upload.return_value = MockUploadResult(
                platform=Platform.YOUTUBE,
                video_path=Path("test.mp4"),
                upload_id=None,
                status="failed",
                error_message="Persistent failure"
            )
            mock_youtube.return_value = mock_yt_instance
            
            upload_manager = UploadManager(mock_config)
            
            failed_result = UploadResult(
                platform=Platform.YOUTUBE,
                video_path=Path("test.mp4"),
                upload_id=None,
                status="failed",
                details={'title': 'Failed Upload', 'description': 'Test', 'tags': [], 'hashtags': []},
                error_message="Initial failure"
            )
            
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                video_path = Path(temp_file.name)
            
            try:
                results = await upload_manager.retry_failed_uploads([failed_result], max_retries=2)
                
                # Should have the failed result after retry attempts
                assert len(results) == 1
                assert results[0].status == "failed"
                assert "Persistent failure" in results[0].error_message
                # Verify upload was called max_retries times plus original
                assert mock_yt_instance.upload.call_count == 2  # max_retries=2, so 2 attempts after original failure
                
            finally:
                # Clean up
                if video_path.exists():
                    video_path.unlink()
    
    @pytest.mark.asyncio
    async def test_save_results_to_db_integration(self):
        """Test the save_results_to_db function integration."""
        from src.uploader.manager import UploadManager, UploadManagerConfig
        from src.uploader.base import Platform
        
        mock_config = MockUploadManagerConfig(
            youtube_credentials={'access_token': 'youtube_token'}
        )
        
        with patch('src.uploader.youtube.YouTubeUploader') as mock_youtube:
            mock_yt_instance = AsyncMock()
            mock_yt_instance.upload.return_value = MockUploadResult(
                platform=Platform.YOUTUBE,
                video_path=Path("test.mp4"),
                upload_id="yt_test_id",
                status="completed"
            )
            mock_youtube.return_value = mock_yt_instance
            
            upload_manager = UploadManager(mock_config)
            
            # Mock the _save_results_to_db method
            with patch.object(upload_manager, '_save_results_to_db') as mock_save:
                with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                    video_path = Path(temp_file.name)
                
                try:
                    await upload_manager.upload_to_all_platforms(
                        video_path=video_path,
                        title="Test Video",
                        description="Test Description",
                        tags=["test"],
                        hashtags=["#test"],
                        languages={Platform.YOUTUBE: "en"}
                    )
                    
                    # Verify that save_results_to_db was called
                    assert mock_save.called
                    # And verify it was called with a list containing at least one result
                    call_args = mock_save.call_args
                    results_passed = call_args[0][0]
                    assert len(results_passed) >= 1
                    assert results_passed[0].platform == Platform.YOUTUBE
                    assert results_passed[0].status == "completed"
                    
                finally:
                    # Clean up
                    if video_path.exists():
                        video_path.unlink()
    
    @pytest.mark.asyncio
    async def test_upload_manager_initialization(self):
        """Test UploadManager initialization with different configurations."""
        from src.uploader.manager import UploadManager, UploadManagerConfig
        from src.uploader.base import Platform
        
        # Test with all credentials
        mock_config_full = MockUploadManagerConfig(
            youtube_credentials={'access_token': 'youtube_token'},
            tiktok_credentials={'access_token': 'tiktok_token'},
            facebook_credentials={'access_token': 'facebook_token'}
        )
        
        upload_manager_full = UploadManager(mock_config_full)
        assert upload_manager_full.uploaders[Platform.YOUTUBE] is not None
        assert upload_manager_full.uploaders[Platform.TIKTOK] is not None
        assert upload_manager_full.uploaders[Platform.FACEBOOK] is not None
        
        # Test with partial credentials
        mock_config_partial = MockUploadManagerConfig(
            youtube_credentials={'access_token': 'youtube_token'},
            facebook_credentials={'access_token': 'facebook_token'}
        )
        
        upload_manager_partial = UploadManager(mock_config_partial)
        assert upload_manager_partial.uploaders[Platform.YOUTUBE] is not None
        assert upload_manager_partial.uploaders[Platform.TIKTOK] is None
        assert upload_manager_partial.uploaders[Platform.FACEBOOK] is not None
    
    @pytest.mark.asyncio
    async def test_upload_manager_with_only_one_platform(self):
        """Test UploadManager with only one platform enabled."""
        from src.uploader.manager import UploadManager, UploadManagerConfig
        from src.uploader.base import Platform
        
        mock_config = MockUploadManagerConfig(
            youtube_credentials={'access_token': 'youtube_token'}
        )
        
        with patch('src.uploader.youtube.YouTubeUploader') as mock_youtube:
            mock_yt_instance = AsyncMock()
            mock_yt_instance.upload.return_value = MockUploadResult(
                platform=Platform.YOUTUBE,
                video_path=Path("test.mp4"),
                upload_id="yt_test_id",
                status="completed"
            )
            mock_youtube.return_value = mock_yt_instance
            
            upload_manager = UploadManager(mock_config)
            
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                video_path = Path(temp_file.name)
            
            try:
                results = await upload_manager.upload_to_all_platforms(
                    video_path=video_path,
                    title="Test Video",
                    description="Test Description",
                    tags=["test"],
                    hashtags=["#test"],
                    languages={Platform.YOUTUBE: "en"}
                )
                
                # Should have one result only from YouTube
                assert len(results) == 1
                assert results[0].platform == Platform.YOUTUBE
                assert results[0].status == "completed"
                
            finally:
                # Clean up
                if video_path.exists():
                    video_path.unlink()
    
    @pytest.mark.asyncio
    async def test_upload_manager_empty_languages_dict(self):
        """Test UploadManager with empty languages dictionary."""
        from src.uploader.manager import UploadManager, UploadManagerConfig
        from src.uploader.base import Platform
        
        mock_config = MockUploadManagerConfig(
            youtube_credentials={'access_token': 'youtube_token'},
            tiktok_credentials={'access_token': 'tiktok_token'},
            facebook_credentials={'access_token': 'facebook_token'}
        )
        
        with patch('src.uploader.youtube.YouTubeUploader') as mock_youtube, \
             patch('src.uploader.tiktok.TikTokUploader') as mock_tiktok, \
             patch('src.uploader.facebook.FacebookUploader') as mock_fb:
            
            mock_yt_instance = AsyncMock()
            mock_yt_instance.upload.return_value = MockUploadResult(
                platform=Platform.YOUTUBE,
                video_path=Path("test.mp4"),
                upload_id="yt_test_id",
                status="completed"
            )
            mock_youtube.return_value = mock_yt_instance
            
            mock_tt_instance = AsyncMock()
            mock_tt_instance.upload.return_value = MockUploadResult(
                platform=Platform.TIKTOK,
                video_path=Path("test.mp4"),
                upload_id="tt_test_id",
                status="completed"
            )
            mock_tiktok.return_value = mock_tt_instance
            
            mock_fb_instance = AsyncMock()
            mock_fb_instance.upload.return_value = MockUploadResult(
                platform=Platform.FACEBOOK,
                video_path=Path("test.mp4"),
                upload_id="fb_test_id",
                status="completed"
            )
            mock_fb.return_value = mock_fb_instance
            
            upload_manager = UploadManager(mock_config)
            
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                video_path = Path(temp_file.name)
            
            try:
                # Pass empty languages dict - should use defaults
                results = await upload_manager.upload_to_all_platforms(
                    video_path=video_path,
                    title="Test Video",
                    description="Test Description",
                    tags=["test"],
                    hashtags=["#test"],
                    languages={}  # Empty languages dict
                )
                
                assert len(results) == 3  # All three platforms
                platforms = [result.platform for result in results]
                assert Platform.YOUTUBE in platforms
                assert Platform.TIKTOK in platforms
                assert Platform.FACEBOOK in platforms
                
            finally:
                # Clean up
                if video_path.exists():
                    video_path.unlink()