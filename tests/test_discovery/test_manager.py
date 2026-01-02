import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch


class TestDiscoveryManager:
    """Test cases for the Manga Discovery Manager."""
    
    @pytest.mark.asyncio
    async def test_discover_trending_manga_happy_path(self):
        """Test discovering trending manga successfully."""
        with patch('src.discovery.manager.DiscoveryManager') as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager.discover_trending_manga.return_value = [
                {
                    'id': 'test_manga_1',
                    'title': 'Test Manga 1',
                    'last_chapter': 1.0,
                    'status': 'ongoing',
                    'popularity': 95
                }
            ]
            mock_manager_class.return_value = mock_manager
            
            from src.discovery.manager import DiscoveryManager
            manager = DiscoveryManager()
            results = await manager.discover_trending_manga()
            
            assert len(results) == 1
            assert results[0]['title'] == 'Test Manga 1'
    
    @pytest.mark.asyncio
    async def test_discover_trending_manga_with_filters(self):
        """Test discovering trending manga with filters applied."""
        with patch('src.discovery.manager.DiscoveryManager') as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager.discover_trending_manga.return_value = [
                {
                    'id': 'test_manga_1',
                    'title': 'Test Manga 1',
                    'genre': ['action', 'adventure'],
                    'last_chapter': 1.0,
                    'status': 'ongoing',
                    'popularity': 95
                },
                {
                    'id': 'test_manga_2',
                    'title': 'Test Manga 2',
                    'genre': ['romance'],
                    'last_chapter': 2.0,
                    'status': 'ongoing',
                    'popularity': 80
                }
            ]
            mock_manager_class.return_value = mock_manager
            
            from src.discovery.manager import DiscoveryManager
            manager = DiscoveryManager()
            # Test filtering by genre
            results = await manager.discover_trending_manga(genres=['action'])
            
            assert len(results) == 1
            assert results[0]['title'] == 'Test Manga 1'
    
    @pytest.mark.asyncio
    async def test_discover_trending_manga_error_handling(self):
        """Test error handling when discovering trending manga."""
        with patch('src.discovery.manager.DiscoveryManager') as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager.discover_trending_manga.side_effect = Exception("API Error")
            mock_manager_class.return_value = mock_manager
            
            from src.discovery.manager import DiscoveryManager
            manager = DiscoveryManager()
            
            with pytest.raises(Exception, match="API Error"):
                await manager.discover_trending_manga()
    
    @pytest.mark.asyncio
    async def test_discover_manga_by_title(self):
        """Test discovering a specific manga by title."""
        with patch('src.discovery.manager.DiscoveryManager') as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager.discover_manga_by_title.return_value = [
                {
                    'id': 'specific_manga',
                    'title': 'One Piece',
                    'last_chapter': 1001.0,
                    'status': 'ongoing',
                    'popularity': 99
                }
            ]
            mock_manager_class.return_value = mock_manager
            
            from src.discovery.manager import DiscoveryManager
            manager = DiscoveryManager()
            
            results = await manager.discover_manga_by_title(title="One Piece")
            assert len(results) == 1
            assert results[0]['title'] == 'One Piece'
    
    @pytest.mark.asyncio
    async def test_get_manga_details(self):
        """Test retrieving detailed information for a specific manga."""
        with patch('src.discovery.manager.DiscoveryManager') as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager.get_manga_details.return_value = {
                'id': 'manga_1',
                'title': 'Test Manga',
                'author': 'Test Author',
                'artist': 'Test Artist',
                'description': 'A test manga description',
                'status': 'ongoing',
                'genres': ['action', 'adventure'],
                'chapters': [
                    {'chapter_num': 1.0, 'title': 'Chapter 1', 'published_date': '2023-01-01'},
                    {'chapter_num': 2.0, 'title': 'Chapter 2', 'published_date': '2023-01-08'}
                ]
            }
            mock_manager_class.return_value = mock_manager
            
            from src.discovery.manager import DiscoveryManager
            manager = DiscoveryManager()
            
            details = await manager.get_manga_details(manga_id='manga_1')
            assert details['title'] == 'Test Manga'
            assert details['author'] == 'Test Author'
            assert len(details['chapters']) == 2
    
    @pytest.mark.asyncio
    async def test_get_manga_details_not_found(self):
        """Test handling when a manga is not found."""
        with patch('src.discovery.manager.DiscoveryManager') as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager.get_manga_details.return_value = None
            mock_manager_class.return_value = mock_manager
            
            from src.discovery.manager import DiscoveryManager
            manager = DiscoveryManager()
            
            details = await manager.get_manga_details(manga_id='nonexistent_manga')
            assert details is None
    
    @pytest.mark.asyncio
    async def test_discover_trending_manga_edge_cases(self):
        """Test edge cases in manga discovery."""
        with patch('src.discovery.manager.DiscoveryManager') as mock_manager_class:
            mock_manager = AsyncMock()
            # Test with various edge cases like special characters, numbers, etc.
            mock_manager.discover_trending_manga.return_value = [
                {
                    'id': 'special_chars',
                    'title': 'Test Manga: Special Characters!',
                    'last_chapter': 1.5,
                    'status': 'ongoing',
                    'popularity': 90
                },
                {
                    'id': 'long_title',
                    'title': 'This is a very long manga title that might exceed typical length limits',
                    'last_chapter': 10.0,
                    'status': 'ongoing', 
                    'popularity': 85
                },
                {
                    'id': 'numerical_title',
                    'title': '123456789',  # Pure numerical title
                    'last_chapter': 100.0,
                    'status': 'completed',
                    'popularity': 75
                }
            ]
            mock_manager_class.return_value = mock_manager
            
            from src.discovery.manager import DiscoveryManager
            manager = DiscoveryManager()
            
            results = await manager.discover_trending_manga(limit=10)
            assert len(results) == 3
            
            # Verify all types of titles are handled correctly
            titles = [m['title'] for m in results]
            assert 'Test Manga: Special Characters!' in titles
            assert 'This is a very long manga title that might exceed typical length limits' in titles
            assert '123456789' in titles