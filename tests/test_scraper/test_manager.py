import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
import tempfile


class TestScraperManager:
    """Test cases for the scraping manager."""
    
    @pytest.mark.asyncio
    async def test_scrape_manga_chapter_happy_path(self):
        """Test the full scraping workflow for a manga chapter."""
        with patch('src.scrapers.manager.MangaDexScraper') as mock_scraper_class:
            mock_scraper = AsyncMock()
            # Mock the get_chapter_images method
            mock_scraper.get_chapter_images.return_value = [
                'https://example.com/image1.jpg',
                'https://example.com/image2.jpg'
            ]
            
            # Mock the download_image method to save mock content
            async def mock_download_image(url, output_path):
                # Create a minimal image-like content for testing
                with open(output_path, 'wb') as f:
                    f.write(b'mock_image_content')
            
            mock_scraper.download_image = mock_download_image
            mock_scraper_class.return_value = mock_scraper
            
            from src.scrapers.manager import ScraperManager
            manager = ScraperManager()
            
            with tempfile.TemporaryDirectory() as temp_dir:
                chapter_data = await manager.scrape_manga_chapter(
                    manga_id='test_manga',
                    chapter_id='test_chapter',
                    output_dir=Path(temp_dir)
                )
                
                assert 'images' in chapter_data
                assert len(chapter_data['images']) == 2
                assert all(Path(img).exists() for img in chapter_data['images'])
                assert chapter_data['manga_id'] == 'test_manga'
                assert chapter_data['chapter_id'] == 'test_chapter'
    
    @pytest.mark.asyncio
    async def test_scrape_manga_chapter_with_validation(self):
        """Test scraping with file validation."""
        with patch('src.scrapers.manager.MangaDexScraper') as mock_scraper_class:
            mock_scraper = AsyncMock()
            mock_scraper.get_chapter_images.return_value = [
                'https://example.com/image1.jpg',
                'https://example.com/image2.jpg'
            ]
            
            async def mock_download_image(url, output_path):
                with open(output_path, 'wb') as f:
                    f.write(b'mock_image_content')
            
            mock_scraper.download_image = mock_download_image
            mock_scraper_class.return_value = mock_scraper
            
            from src.scrapers.manager import ScraperManager
            manager = ScraperManager()
            
            with tempfile.TemporaryDirectory() as temp_dir:
                chapter_data = await manager.scrape_manga_chapter(
                    manga_id='test_manga',
                    chapter_id='test_chapter', 
                    output_dir=Path(temp_dir),
                    validate_downloads=True
                )
                
                assert 'images' in chapter_data
                assert len(chapter_data['images']) == 2
                # Validate the files exist and have content
                for img_path in chapter_data['images']:
                    assert Path(img_path).exists()
                    assert Path(img_path).stat().st_size > 0
    
    @pytest.mark.asyncio
    async def test_scrape_manga_chapter_error_handling(self):
        """Test error handling in the scraping workflow."""
        with patch('src.scrapers.manager.MangaDexScraper') as mock_scraper_class:
            mock_scraper = AsyncMock()
            mock_scraper.get_chapter_images.side_effect = Exception("API Error")
            mock_scraper_class.return_value = mock_scraper
            
            from src.scrapers.manager import ScraperManager
            manager = ScraperManager()
            
            with tempfile.TemporaryDirectory() as temp_dir:
                with pytest.raises(Exception, match="API Error"):
                    await manager.scrape_manga_chapter(
                        manga_id='test_manga',
                        chapter_id='test_chapter',
                        output_dir=Path(temp_dir)
                    )
    
    @pytest.mark.asyncio
    async def test_scrape_manga_chapter_missing_images(self):
        """Test handling when no images are found for a chapter."""
        with patch('src.scrapers.manager.MangaDexScraper') as mock_scraper_class:
            mock_scraper = AsyncMock()
            mock_scraper.get_chapter_images.return_value = []
            mock_scraper_class.return_value = mock_scraper
            
            from src.scrapers.manager import ScraperManager
            manager = ScraperManager()
            
            with tempfile.TemporaryDirectory() as temp_dir:
                with pytest.raises(ValueError, match="No images found for chapter"):
                    await manager.scrape_manga_chapter(
                        manga_id='test_manga',
                        chapter_id='test_chapter',
                        output_dir=Path(temp_dir)
                    )
    
    @pytest.mark.asyncio
    async def test_scrape_multiple_chapters(self):
        """Test scraping multiple chapters in parallel."""
        with patch('src.scrapers.manager.MangaDexScraper') as mock_scraper_class:
            mock_scraper = AsyncMock()
            mock_scraper.get_chapter_images.side_effect = [
                ['https://example.com/ch1_img1.jpg', 'https://example.com/ch1_img2.jpg'],
                ['https://example.com/ch2_img1.jpg', 'https://example.com/ch2_img2.jpg']
            ]
            
            async def mock_download_image(url, output_path):
                with open(output_path, 'wb') as f:
                    f.write(b'mock_image_content')
            
            mock_scraper.download_image = mock_download_image
            mock_scraper_class.return_value = mock_scraper
            
            from src.scrapers.manager import ScraperManager
            manager = ScraperManager()
            
            chapters_to_scrape = [
                {'manga_id': 'test_manga', 'chapter_id': 'ch1', 'output_dir': tempfile.mkdtemp()},
                {'manga_id': 'test_manga', 'chapter_id': 'ch2', 'output_dir': tempfile.mkdtemp()}
            ]
            
            results = await manager.scrape_multiple_chapters(chapters_to_scrape)
            
            assert len(results) == 2
            assert all('images' in result for result in results)
            assert all(len(result['images']) == 2 for result in results)
    
    @pytest.mark.asyncio
    async def test_scrape_multiple_chapters_with_partial_failure(self):
        """Test handling when some chapters fail during multi-chapter scraping."""
        with patch('src.scrapers.manager.MangaDexScraper') as mock_scraper_class:
            mock_scraper = AsyncMock()
            mock_scraper.get_chapter_images.side_effect = [
                ['https://example.com/ch1_img1.jpg'],  # First chapter succeeds
                Exception("Chapter 2 API Error")      # Second chapter fails
            ]
            
            async def mock_download_image(url, output_path):
                with open(output_path, 'wb') as f:
                    f.write(b'mock_image_content')
            
            mock_scraper.download_image = mock_download_image
            mock_scraper_class.return_value = mock_scraper
            
            from src.scrapers.manager import ScraperManager
            manager = ScraperManager()
            
            chapters_to_scrape = [
                {'manga_id': 'test_manga', 'chapter_id': 'ch1', 'output_dir': tempfile.mkdtemp()},
                {'manga_id': 'test_manga', 'chapter_id': 'ch2', 'output_dir': tempfile.mkdtemp()}
            ]
            
            # Only successful results should be returned
            results = await manager.scrape_multiple_chapters(chapters_to_scrape)
            
            # Should have 1 result (the successful one) despite the error
            assert len(results) == 1
            assert results[0]['chapter_id'] == 'ch1'
            assert len(results[0]['images']) == 1
    
    @pytest.mark.asyncio
    async def test_scrape_chapter_with_custom_image_processing(self):
        """Test scraping with custom image processing options."""
        with patch('src.scrapers.manager.MangaDexScraper') as mock_scraper_class:
            mock_scraper = AsyncMock()
            mock_scraper.get_chapter_images.return_value = [
                'https://example.com/image1.jpg'
            ]
            
            async def mock_download_image(url, output_path):
                with open(output_path, 'wb') as f:
                    f.write(b'mock_image_content')
            
            mock_scraper.download_image = mock_download_image
            mock_scraper_class.return_value = mock_scraper
            
            from src.scrapers.manager import ScraperManager
            manager = ScraperManager()
            
            with tempfile.TemporaryDirectory() as temp_dir:
                chapter_data = await manager.scrape_manga_chapter(
                    manga_id='test_manga',
                    chapter_id='test_chapter',
                    output_dir=Path(temp_dir),
                    resize_images=True,
                    max_width=1080,
                    max_height=1920
                )
                
                assert 'images' in chapter_data
                assert len(chapter_data['images']) == 1
                # Verify that the image exists
                assert Path(chapter_data['images'][0]).exists()
    
    @pytest.mark.asyncio
    async def test_scrape_chapter_with_invalid_parameters(self):
        """Test scraping with invalid parameters."""
        from src.scrapers.manager import ScraperManager
        manager = ScraperManager()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test with invalid manga_id
            with pytest.raises(ValueError, match="Invalid manga_id"):
                await manager.scrape_manga_chapter(
                    manga_id='',  # Empty manga_id
                    chapter_id='test_chapter',
                    output_dir=Path(temp_dir)
                )
            
            # Test with invalid chapter_id
            with pytest.raises(ValueError, match="Invalid chapter_id"):
                await manager.scrape_manga_chapter(
                    manga_id='test_manga',
                    chapter_id='',  # Empty chapter_id
                    output_dir=Path(temp_dir)
                )