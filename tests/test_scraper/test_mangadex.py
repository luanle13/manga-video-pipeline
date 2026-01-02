import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path


class TestMangaDexScraper:
    """Test cases for MangaDex scraping functionality."""
    
    @pytest.mark.asyncio
    async def test_scrape_chapter_images_happy_path(self):
        """Test scraping chapter images successfully."""
        with patch('src.scrapers.mangadex.MangaDexClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get_chapter_images.return_value = [
                'https://example.com/image1.jpg',
                'https://example.com/image2.jpg',
                'https://example.com/image3.jpg'
            ]
            mock_client.return_value = mock_instance
            
            from src.scrapers.mangadex import MangaDexScraper
            scraper = MangaDexScraper()
            
            images = await scraper.get_chapter_images('manga_id', 'chapter_id')
            
            assert len(images) == 3
            assert images[0] == 'https://example.com/image1.jpg'
            assert images[1] == 'https://example.com/image2.jpg'
            assert images[2] == 'https://example.com/image3.jpg'
            
            mock_instance.get_chapter_images.assert_called_once_with('manga_id', 'chapter_id')
    
    @pytest.mark.asyncio
    async def test_scrape_chapter_images_empty_result(self):
        """Test handling of empty results from chapter scraping."""
        with patch('src.scrapers.mangadex.MangaDexClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get_chapter_images.return_value = []
            mock_client.return_value = mock_instance
            
            from src.scrapers.mangadex import MangaDexScraper
            scraper = MangaDexScraper()
            
            images = await scraper.get_chapter_images('manga_id', 'chapter_id')
            
            assert len(images) == 0
            mock_instance.get_chapter_images.assert_called_once_with('manga_id', 'chapter_id')
    
    @pytest.mark.asyncio 
    async def test_scrape_chapter_images_error_handling(self):
        """Test error handling when scraping chapter images."""
        with patch('src.scrapers.mangadex.MangaDexClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get_chapter_images.side_effect = Exception("Scraping Error")
            mock_client.return_value = mock_instance
            
            from src.scrapers.mangadex import MangaDexScraper
            scraper = MangaDexScraper()
            
            with pytest.raises(Exception, match="Scraping Error"):
                await scraper.get_chapter_images('manga_id', 'chapter_id')
    
    @pytest.mark.asyncio
    async def test_download_image_simple(self):
        """Test downloading a single image."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.content = b'mock_image_content'
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            
            from src.scrapers.mangadex import MangaDexScraper
            scraper = MangaDexScraper()
            
            # Create a temporary output directory for testing
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / 'test_image.jpg'
                
                await scraper.download_image('https://example.com/image.jpg', output_path)
                
                # Verify the image was "downloaded" (mocked)
                mock_client.get.assert_called_once_with('https://example.com/image.jpg')
                assert output_path.exists()
                assert output_path.read_bytes() == b'mock_image_content'
    
    @pytest.mark.asyncio
    async def test_download_image_with_retry(self):
        """Test image download with retry logic."""
        # Mock client that fails on first try but succeeds on second
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_response_fail = AsyncMock()
            mock_response_fail.status_code = 500
            mock_response_success = AsyncMock()
            mock_response_success.status_code = 200
            mock_response_success.content = b'mock_image_content'
            
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=[mock_response_fail, mock_response_success])
            
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            
            from src.scrapers.mangadex import MangaDexScraper
            scraper = MangaDexScraper()
            
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / 'test_image.jpg'
                
                await scraper.download_image('https://example.com/image.jpg', output_path)
                
                # Verify the client was called twice (1st failure, 2nd success)
                assert mock_client.get.call_count == 2
    
    @pytest.mark.asyncio
    async def test_download_image_failure_after_retries(self):
        """Test image download failure after all retries."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_response = AsyncMock()
            mock_response.status_code = 500
            
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response  # Always fail
            
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            
            from src.scrapers.mangadex import MangaDexScraper
            scraper = MangaDexScraper()
            
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / 'test_image.jpg'
                
                with pytest.raises(Exception, match=r"Failed to download image after \d+ attempts"):
                    await scraper.download_image('https://example.com/image.jpg', output_path)
    
    @pytest.mark.asyncio
    async def test_scrape_multiple_chapters(self):
        """Test scraping multiple chapters at once."""
        with patch('src.scrapers.mangadex.MangaDexClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get_chapter_images.side_effect = [
                ['https://example.com/ch1_img1.jpg', 'https://example.com/ch1_img2.jpg'],
                ['https://example.com/ch2_img1.jpg', 'https://example.com/ch2_img2.jpg']
            ]
            mock_client.return_value = mock_instance
            
            from src.scrapers.mangadex import MangaDexScraper
            scraper = MangaDexScraper()
            
            chapters_data = await scraper.get_multiple_chapters_images([
                ('manga_id', 'chapter_1'),
                ('manga_id', 'chapter_2')
            ])
            
            assert len(chapters_data) == 2
            assert len(chapters_data[0]) == 2  # Chapter 1 has 2 images
            assert len(chapters_data[1]) == 2  # Chapter 2 has 2 images
            assert chapters_data[0][0] == 'https://example.com/ch1_img1.jpg'
            assert chapters_data[1][0] == 'https://example.com/ch2_img1.jpg'