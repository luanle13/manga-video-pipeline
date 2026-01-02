import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
from dataclasses import dataclass


@dataclass
class MockSummaryResult:
    """Mock class for SummaryResult."""
    script: str
    word_count: int
    estimated_duration: int


class TestMangaSummarizer:
    """Test cases for the Manga Summarizer."""
    
    @pytest.mark.asyncio
    async def test_summarize_chapter_happy_path(self):
        """Test the summarize_chapter function with valid inputs."""
        with patch('openai.AsyncOpenAI') as mock_client:
            mock_instance = AsyncMock()
            mock_response = AsyncMock()
            mock_response.choices = [AsyncMock()]
            mock_response.choices[0].message = AsyncMock()
            mock_response.choices[0].message.content = "This is a test summary script for the manga chapter. It contains exciting plot developments."
            mock_instance.chat.completions.create.return_value = mock_response
            mock_client.return_value = mock_instance
            
            from src.ai.summarizer import MangaSummarizer
            summarizer = MangaSummarizer(api_key='test_key')
            
            # Create temporary image paths for testing
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                # Create mock image files
                temp_images = []
                for i in range(3):
                    img_path = Path(temp_dir) / f"mock_image_{i}.jpg"
                    with open(img_path, 'wb') as f:
                        f.write(b'mock_image_content')
                    temp_images.append(img_path)
                
                result = await summarizer.summarize_chapter(
                    images=temp_images,
                    manga_title="One Piece",
                    chapter_number=1001.0,
                    language="en",
                    target_duration=60
                )
                
                # Verify the result
                assert result.script == "This is a test summary script for the manga chapter. It contains exciting plot developments."
                assert result.word_count > 0
                assert result.estimated_duration > 0
                
                # Verify the API was called correctly
                mock_instance.chat.completions.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_summarize_chapter_with_vietnamese_language(self):
        """Test the summarize_chapter function with Vietnamese language."""
        with patch('openai.AsyncOpenAI') as mock_client:
            mock_instance = AsyncMock()
            mock_response = AsyncMock()
            mock_response.choices = [AsyncMock()]
            mock_response.choices[0].message = AsyncMock()
            mock_response.choices[0].message.content = "Đây là một đoạn tóm tắt thử nghiệm cho chương truyện. Nó chứa đựng những phát triển cốt truyện thú vị."
            mock_instance.chat.completions.create.return_value = mock_response
            mock_client.return_value = mock_instance
            
            from src.ai.summarizer import MangaSummarizer
            summarizer = MangaSummarizer(api_key='test_key')
            
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_images = []
                for i in range(2):
                    img_path = Path(temp_dir) / f"mock_image_{i}.jpg"
                    with open(img_path, 'wb') as f:
                        f.write(b'mock_image_content')
                    temp_images.append(img_path)
                
                result = await summarizer.summarize_chapter(
                    images=temp_images,
                    manga_title="One Piece",
                    chapter_number=1001.0,
                    language="vn",  # Vietnamese
                    target_duration=60
                )
                
                assert "phát triển cốt truyện" in result.script
                assert result.word_count > 0
                assert result.estimated_duration > 0
    
    @pytest.mark.asyncio
    async def test_summarize_chapter_unsupported_language(self):
        """Test error handling for unsupported language."""
        from src.ai.summarizer import MangaSummarizer
        summarizer = MangaSummarizer(api_key='test_key')
        
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_images = []
            for i in range(2):
                img_path = Path(temp_dir) / f"mock_image_{i}.jpg"
                with open(img_path, 'wb') as f:
                    f.write(b'mock_image_content')
                temp_images.append(img_path)
            
            with pytest.raises(ValueError, match="Unsupported language: fr"):
                await summarizer.summarize_chapter(
                    images=temp_images,
                    manga_title="One Piece",
                    chapter_number=1001.0,
                    language="fr",  # French is not supported
                    target_duration=60
                )
    
    @pytest.mark.asyncio
    async def test_summarize_chapter_api_error(self):
        """Test error handling when the OpenAI API fails."""
        with patch('openai.AsyncOpenAI') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.chat.completions.create.side_effect = Exception("API Error")
            mock_client.return_value = mock_instance
            
            from src.ai.summarizer import MangaSummarizer
            summarizer = MangaSummarizer(api_key='test_key')
            
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_images = []
                for i in range(2):
                    img_path = Path(temp_dir) / f"mock_image_{i}.jpg"
                    with open(img_path, 'wb') as f:
                        f.write(b'mock_image_content')
                    temp_images.append(img_path)
                
                with pytest.raises(Exception, match="API Error"):
                    await summarizer.summarize_chapter(
                        images=temp_images,
                        manga_title="One Piece",
                        chapter_number=1001.0,
                        language="en",
                        target_duration=60
                    )
    
    @pytest.mark.asyncio
    async def test_summarize_chapter_with_large_image_set(self):
        """Test summarizing with a large set of images (should select key images)."""
        with patch('openai.AsyncOpenAI') as mock_client:
            mock_instance = AsyncMock()
            mock_response = AsyncMock()
            mock_response.choices = [AsyncMock()]
            mock_response.choices[0].message = AsyncMock()
            mock_response.choices[0].message.content = "Detailed summary of a large chapter."
            mock_instance.chat.completions.create.return_value = mock_response
            mock_client.return_value = mock_instance
            
            from src.ai.summarizer import MangaSummarizer
            summarizer = MangaSummarizer(api_key='test_key')
            
            import tempfile
            from pathlib import Path
            with tempfile.TemporaryDirectory() as temp_dir:
                # Create many mock image files (more than the max selection)
                temp_images = []
                for i in range(20):  # More than 12 images
                    img_path = Path(temp_dir) / f"mock_image_{i:02d}.jpg"
                    with open(img_path, 'wb') as f:
                        f.write(b'mock_image_content')
                    temp_images.append(img_path)
                
                result = await summarizer.summarize_chapter(
                    images=temp_images,
                    manga_title="One Piece",
                    chapter_number=1001.0,
                    language="en",
                    target_duration=60
                )
                
                # Verify that it still works with large image sets
                assert result.script == "Detailed summary of a large chapter."
                assert result.word_count > 0
                assert result.estimated_duration > 0
    
    @pytest.mark.asyncio
    async def test_summarize_chapter_retry_logic(self):
        """Test the retry logic for API calls."""
        with patch('openai.AsyncOpenAI') as mock_client:
            mock_instance = AsyncMock()
            # Simulate a temporary failure followed by success
            mock_instance.chat.completions.create = AsyncMock(
                side_effect=[
                    Exception("Rate limit exceeded"),  # First call fails
                    AsyncMock(choices=[AsyncMock(message=AsyncMock(content="Successful retry"))])  # Second call succeeds
                ]
            )
            mock_client.return_value = mock_instance
            
            from src.ai.summarizer import MangaSummarizer
            summarizer = MangaSummarizer(api_key='test_key')
            
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_images = []
                for i in range(2):
                    img_path = Path(temp_dir) / f"mock_image_{i}.jpg"
                    with open(img_path, 'wb') as f:
                        f.write(b'mock_image_content')
                    temp_images.append(img_path)
                
                # This should ultimately succeed after retry
                result = await summarizer.summarize_chapter(
                    images=temp_images,
                    manga_title="One Piece",
                    chapter_number=1001.0,
                    language="en",
                    target_duration=60
                )
                
                assert result.script == "Successful retry"
                # Verify that create was called twice (once failed, once succeeded)
                assert mock_instance.chat.completions.create.call_count == 2
    
    @pytest.mark.asyncio
    async def test_synchronous_summarize_chapter(self):
        """Test the synchronous version of the summarize_chapter function."""
        with patch('openai.AsyncOpenAI') as mock_client:
            mock_instance = AsyncMock()
            mock_response = AsyncMock()
            mock_response.choices = [AsyncMock()]
            mock_response.choices[0].message = AsyncMock()
            mock_response.choices[0].message.content = "Synchronous test summary."
            mock_instance.chat.completions.create.return_value = mock_response
            mock_client.return_value = mock_instance
            
            from src.ai.summarizer import summarize_chapter
            
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_images = []
                for i in range(2):
                    img_path = Path(temp_dir) / f"mock_image_{i}.jpg"
                    with open(img_path, 'wb') as f:
                        f.write(b'mock_image_content')
                    temp_images.append(img_path)
                
                # Call the synchronous version
                result = await summarize_chapter(
                    images=temp_images,
                    manga_title="One Piece",
                    chapter_number=1001.0,
                    language="en",
                    target_duration=60
                )
                
                assert result.script == "Synchronous test summary."
                assert result.word_count > 0
                assert result.estimated_duration > 0