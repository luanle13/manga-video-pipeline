import asyncio
import httpx
from typing import Any, List
from ..config import get_settings


class MangaDiscovery:
    """Discover trending manga from various sources."""
    
    def __init__(self):
        self.client = httpx.AsyncClient()
        self.settings = get_settings()
        self.sources = ["mangadex", "myanimelist", "mangasee"]  # Using default sources

    async def get_trending_manga(self) -> list[dict[str, Any]]:
        """Fetch trending manga from all configured sources."""
        all_manga = []
        
        for source in self.sources:
            if source == "mangadex":
                manga = await self._get_trending_from_mangadex()
                all_manga.extend(manga)
            elif source == "myanimelist":
                manga = await self._get_trending_from_myanimelist()
                all_manga.extend(manga)
            elif source == "mangasee":
                manga = await self._get_trending_from_mangasee()
                all_manga.extend(manga)
        
        # Remove duplicates by manga ID
        unique_manga = []
        seen_ids = set()
        for manga in all_manga:
            manga_id = manga.get('id')
            if manga_id not in seen_ids:
                seen_ids.add(manga_id)
                unique_manga.append(manga)
        
        return unique_manga

    async def _get_trending_from_mangadex(self) -> list[dict[str, Any]]:
        """Fetch trending manga from MangaDex."""
        try:
            url = f"https://api.mangadex.org/manga"
            params = {
                "limit": 20,
                "order[followedCount]": "desc"
            }
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            manga_list = []
            
            for item in data.get('data', []):
                manga_info = {
                    'id': item.get('id'),
                    'title': item.get('attributes', {}).get('title', {}).get('en', 'Unknown'),
                    'description': item.get('attributes', {}).get('description', {}).get('en', ''),
                    'source': 'mangadex',
                    'cover_art': await self._get_cover_art(item.get('id'))
                }
                manga_list.append(manga_info)
                
            return manga_list
        except Exception as e:
            print(f"Error fetching from MangaDex: {e}")
            return []

    async def _get_trending_from_myanimelist(self) -> list[dict[str, Any]]:
        """Fetch trending manga from MyAnimeList."""
        # This is a placeholder implementation
        # Real implementation would need to handle MAL's API or scraping
        print("Fetching from MyAnimeList is not fully implemented yet")
        return []

    async def _get_trending_from_mangasee(self) -> list[dict[str, Any]]:
        """Fetch trending manga from MangaSee."""
        # This is a placeholder implementation
        # Real implementation would need to handle MangaSee's structure
        print("Fetching from MangaSee is not fully implemented yet")
        return []

    async def _get_cover_art(self, manga_id: str) -> str:
        """Get the cover art URL for a manga."""
        try:
            url = f"https://api.mangadex.org/manga/{manga_id}/aggregate"
            response = await self.client.get(url)
            response.raise_for_status()
            
            data = response.json()
            relationships = data.get('data', {}).get('relationships', [])
            
            for rel in relationships:
                if rel.get('type') == 'cover_art':
                    cover_id = rel.get('id')
                    cover_url = f"https://uploads.mangadex.org/covers/{manga_id}/{cover_id}.512.jpg"
                    return cover_url
                    
            return ""
        except Exception as e:
            print(f"Error getting cover art for {manga_id}: {e}")
            return ""


# Singleton instance
discovery = MangaDiscovery()