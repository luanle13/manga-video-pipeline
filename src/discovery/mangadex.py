import httpx
from datetime import datetime
from typing import Any
from .base import DiscoverySource, MangaInfo, ChapterInfo


class MangaDexSource(DiscoverySource):
    """MangaDex API implementation for discovery."""
    
    def __init__(self):
        self.base_url = "https://api.mangadex.org"
        self.client = httpx.AsyncClient(
            headers={"User-Agent": "MangaVideoPipeline/1.0"},
            timeout=30.0
        )
        # Rate limiting: max 5 requests per second
        self.rate_limit_interval = 0.2  # 1/5 second = 0.2 seconds
    
    async def get_trending(self, limit: int = 20) -> list[MangaInfo]:
        """Get trending manga from MangaDex API."""
        try:
            # MangaDex API doesn't have a direct "trending" endpoint
            # We'll use the manga list ordered by followedCount as a proxy for trending
            params = {
                "limit": limit,
                "order[followedCount]": "desc",
                "contentRating[]": ["safe", "suggestive", "erotica", "pornographic"],  # Include all content ratings
                "availableTranslatedLanguage[]": ["en"],  # Only English translations
                "includes[]": ["cover_art", "author", "artist"]
            }
            
            response = await self.client.get(f"{self.base_url}/manga", params=params)
            response.raise_for_status()
            
            data = response.json()
            mangas = []
            
            for item in data.get('data', []):
                manga_id = item.get('id')
                attributes = item.get('attributes', {})
                
                # Get cover URL
                cover_url = await self._get_cover_url(manga_id)
                
                # Extract genres (tags)
                tags = attributes.get('tags', [])
                genres = [tag['attributes']['name'].get('en', 'Unknown') for tag in tags]
                
                manga_info = MangaInfo(
                    source='mangadex',
                    source_id=manga_id,
                    title=attributes.get('title', {}).get('en', 'Unknown'),
                    cover_url=cover_url,
                    trending_rank=None,  # MangaDex doesn't provide a specific trending rank
                    genres=genres
                )
                mangas.append(manga_info)
                
            return mangas
        except Exception as e:
            print(f"Error fetching trending manga from MangaDex: {e}")
            return []
    
    async def get_chapters(self, manga_id: str) -> list[ChapterInfo]:
        """Get all chapters for a specific manga from MangaDex."""
        try:
            # Get chapters for the manga
            params = {
                "manga": manga_id,
                "translatedLanguage[]": ["en"],  # English translations only
                "order[chapter]": "asc",
                "limit": 100  # Get up to 100 chapters at a time
            }
            
            chapters = []
            offset = 0
            
            while True:
                params["offset"] = offset
                response = await self.client.get(f"{self.base_url}/manga/{manga_id}/feed", params=params)
                response.raise_for_status()
                
                data = response.json()
                items = data.get('data', [])
                
                if not items:
                    break  # No more chapters
                
                for item in items:
                    chapter_id = item.get('id')
                    attributes = item.get('attributes', {})
                    
                    # Handle potentially missing chapter number
                    chapter_num_str = attributes.get('chapter')
                    if chapter_num_str is not None:
                        try:
                            chapter_number = float(chapter_num_str)
                        except (ValueError, TypeError):
                            # If chapter number is not a valid float, skip this chapter
                            continue
                    else:
                        # If no chapter number, skip this entry
                        continue
                    
                    # Format chapter title
                    chapter_title = f"Chapter {chapter_number}"
                    if attributes.get('title'):
                        chapter_title += f": {attributes['title']}"
                    
                    # Parse published date
                    published_at = None
                    publish_date_str = attributes.get('publishAt')
                    if publish_date_str:
                        try:
                            published_at = datetime.fromisoformat(publish_date_str.replace('Z', '+00:00'))
                        except ValueError:
                            pass  # If parsing fails, keep as None
                    
                    chapter_info = ChapterInfo(
                        chapter_number=chapter_number,
                        source_url=f"https://mangadex.org/chapter/{chapter_id}",
                        title=chapter_title,
                        published_at=published_at
                    )
                    chapters.append(chapter_info)
                
                # Check if we received fewer items than the limit, indicating we're done
                if len(items) < params["limit"]:
                    break
                
                offset += params["limit"]
            
            return chapters
        except Exception as e:
            print(f"Error fetching chapters for manga {manga_id} from MangaDex: {e}")
            return []
    
    async def get_new_chapters(self, manga_id: str, since: datetime) -> list[ChapterInfo]:
        """Get new chapters for a specific manga since a given date."""
        all_chapters = await self.get_chapters(manga_id)
        
        # Filter chapters that were published after the 'since' date
        new_chapters = []
        for chapter in all_chapters:
            if chapter.published_at and chapter.published_at > since:
                new_chapters.append(chapter)
        
        return new_chapters
    
    async def _get_cover_url(self, manga_id: str) -> str | None:
        """Get the cover URL for a manga."""
        try:
            # Get manga details including relationships
            response = await self.client.get(f"{self.base_url}/manga/{manga_id}")
            response.raise_for_status()
            
            data = response.json()
            relationships = data.get('data', {}).get('relationships', [])
            
            # Look for cover_art relationship
            for rel in relationships:
                if rel.get('type') == 'cover_art':
                    cover_id = rel.get('id')
                    if cover_id:
                        # Construct the cover URL
                        # MangaDex cover images follow this pattern: https://uploads.mangadex.org/covers/{manga_id}/{cover_id}.512.jpg
                        return f"https://uploads.mangadex.org/covers/{manga_id}/{cover_id}.512.jpg"
            
            return None
        except Exception as e:
            print(f"Error getting cover for manga {manga_id}: {e}")
            return None
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()