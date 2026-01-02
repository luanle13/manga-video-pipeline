import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from pathlib import Path


class TestMangaDexDiscovery:
    """Test cases for MangaDex API integration."""
    
    @pytest.mark.asyncio
    async def test_discover_trending_manga_happy_path(self):
        """Test discovering trending manga successfully."""
        # Mock the MangaDex API response
        with patch('src.discovery.mangadex.MangaDexAPI') as mock_api:
            mock_instance = AsyncMock()
            mock_instance.get_trending_manga.return_value = [
                {
                    'id': 'test_manga_1',
                    'title': 'Test Manga 1',
                    'last_chapter': 1.0,
                    'status': 'ongoing',
                    'popularity': 95
                },
                {
                    'id': 'test_manga_2', 
                    'title': 'Test Manga 2',
                    'last_chapter': 5.5,
                    'status': 'ongoing',
                    'popularity': 87
                }
            ]
            mock_api.return_value = mock_instance
            
            # Import the actual discovery module
            from src.discovery.mangadex import MangaDexDiscoverer
            discoverer = MangaDexDiscoverer()
            
            # Perform discovery
            results = await discoverer.discover_trending_manga(limit=10)
            
            # Assertions
            assert len(results) == 2
            assert results[0]['title'] == 'Test Manga 1'
            assert results[1]['title'] == 'Test Manga 2'
            
            # Verify the API was called correctly
            mock_instance.get_trending_manga.assert_called_once_with(limit=10)
    
    @pytest.mark.asyncio
    async def test_discover_trending_manga_error_handling(self):
        """Test error handling when discovering trending manga."""
        # Mock the MangaDex API to raise an exception
        with patch('src.discovery.mangadex.MangaDexAPI') as mock_api:
            mock_instance = AsyncMock()
            mock_instance.get_trending_manga.side_effect = Exception("API Error")
            mock_api.return_value = mock_instance
            
            from src.discovery.mangadex import MangaDexDiscoverer
            discoverer = MangaDexDiscoverer()
            
            # Expect an exception to be raised
            with pytest.raises(Exception, match="API Error"):
                await discoverer.discover_trending_manga(limit=10)
    
    @pytest.mark.asyncio
    async def test_discover_trending_manga_empty_response(self):
        """Test handling of empty response from MangaDex."""
        with patch('src.discovery.mangadex.MangaDexAPI') as mock_api:
            mock_instance = AsyncMock()
            mock_instance.get_trending_manga.return_value = []
            mock_api.return_value = mock_instance
            
            from src.discovery.mangadex import MangaDexDiscoverer
            discoverer = MangaDexDiscoverer()
            
            results = await discoverer.discover_trending_manga(limit=10)
            
            assert len(results) == 0
            mock_instance.get_trending_manga.assert_called_once_with(limit=10)
    
    @pytest.mark.asyncio
    async def test_discover_specific_manga_by_title(self):
        """Test discovering a specific manga by title."""
        with patch('src.discovery.mangadex.MangaDexAPI') as mock_api:
            mock_instance = AsyncMock()
            mock_instance.search_manga.return_value = [
                {
                    'id': 'specific_manga',
                    'title': 'One Piece',
                    'last_chapter': 1001.0,
                    'status': 'ongoing',
                    'popularity': 99
                }
            ]
            mock_api.return_value = mock_instance
            
            from src.discovery.mangadex import MangaDexDiscoverer
            discoverer = MangaDexDiscoverer()
            
            results = await discoverer.discover_manga_by_title(title="One Piece")
            
            assert len(results) == 1
            assert results[0]['title'] == 'One Piece'
            assert results[0]['last_chapter'] == 1001.0
            mock_instance.search_manga.assert_called_once_with("One Piece")


class TestDiscoveryManager:
    """Test cases for the Manga Discovery Manager."""
    
    @pytest.mark.asyncio
    async def test_discovery_manager_initialization(self):
        """Test initialization of the discovery manager."""
        from src.discovery.manager import DiscoveryManager
        manager = DiscoveryManager()
        
        # Check that it has the expected discovery sources
        assert hasattr(manager, 'sources')
        assert len(manager.sources) >= 1  # At least MangaDex
    
    @pytest.mark.asyncio
    async def test_aggregate_discoveries(self):
        """Test aggregating discoveries from multiple sources."""
        from src.discovery.manager import DiscoveryManager
        
        mock_source1 = AsyncMock()
        mock_source1.discover_trending_manga.return_value = [
            {'id': 'source1_manga1', 'title': 'Source1 Manga 1', 'last_chapter': 1.0}
        ]
        
        mock_source2 = AsyncMock()
        mock_source2.discover_trending_manga.return_value = [
            {'id': 'source2_manga1', 'title': 'Source2 Manga 1', 'last_chapter': 2.0}
        ]
        
        manager = DiscoveryManager(sources=[mock_source1, mock_source2])
        results = await manager.aggregate_discoveries()
        
        assert len(results) == 2
        assert results[0]['title'] == 'Source1 Manga 1'
        assert results[1]['title'] == 'Source2 Manga 1'
    
    @pytest.mark.asyncio
    async def test_aggregate_discoveries_with_error_source(self):
        """Test aggregating discoveries when one source fails."""
        from src.discovery.manager import DiscoveryManager
        
        mock_source1 = AsyncMock()
        mock_source1.discover_trending_manga.return_value = [
            {'id': 'source1_manga1', 'title': 'Source1 Manga 1', 'last_chapter': 1.0}
        ]
        
        mock_source2 = AsyncMock()
        mock_source2.discover_trending_manga.side_effect = Exception("Source 2 Error")
        
        manager = DiscoveryManager(sources=[mock_source1, mock_source2])
        results = await manager.aggregate_discoveries()
        
        # Should still return results from successful sources
        assert len(results) == 1
        assert results[0]['title'] == 'Source1 Manga 1'