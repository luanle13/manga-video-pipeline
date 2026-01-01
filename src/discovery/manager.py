import asyncio
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Any
from .base import MangaInfo, ChapterInfo
from .mangadex import MangaDexSource
from .webtoon import WebtoonSource
from ..database import MangaRepository, ChapterRepository, get_async_db


class DiscoveryManager:
    """Main manager for manga discovery across multiple sources."""
    
    def __init__(self):
        self.sources = {
            'mangadex': MangaDexSource(),
            'webtoon': WebtoonSource()
        }
    
    async def discover_trending(self, limit: int = 20) -> list[MangaInfo]:
        """Discover trending manga from all sources."""
        all_manga = []
        
        # Fetch trending from each source
        for source_name, source in self.sources.items():
            try:
                trending = await source.get_trending(limit=limit)
                for manga in trending:
                    # Add source name to manga info for tracking
                    all_manga.append(manga)
            except Exception as e:
                print(f"Error fetching trending from {source_name}: {e}")
        
        # Deduplicate by title similarity (using fuzzy matching)
        deduplicated_manga = self._deduplicate_manga(all_manga)
        
        # Save to database
        async for db in get_async_db():
            for manga in deduplicated_manga:
                # Check if manga already exists in the database
                existing_manga = await MangaRepository.get_by_source_id(db, manga.source_id)
                if not existing_manga:
                    # Create new manga record
                    manga_data = {
                        'source': manga.source,
                        'source_id': manga.source_id,
                        'title': manga.title,
                        'cover_url': manga.cover_url,
                        'trending_rank': manga.trending_rank,
                        'is_active': True
                    }
                    await MangaRepository.create(db, manga_data)
                else:
                    # Update existing manga if needed
                    await MangaRepository.update(db, existing_manga.id, {
                        'title': manga.title,
                        'cover_url': manga.cover_url,
                        'trending_rank': manga.trending_rank,
                        'last_checked_at': datetime.utcnow()
                    })
        
        return deduplicated_manga
    
    async def check_new_chapters(self) -> list[ChapterInfo]:
        """Check for new chapters in previously discovered manga."""
        new_chapters = []
        
        # Get manga from database that we've previously discovered
        async for db in get_async_db():
            from sqlalchemy import select
            from ..database.models import Manga
            stmt = select(Manga).where(Manga.is_active == True)  # noqa: E712
            result = await db.execute(stmt)
            manga_list = result.scalars().all()
        
        # For each manga, check for new chapters
        for manga in manga_list:
            try:
                source = self.sources.get(manga.source)
                if not source:
                    continue
                
                # For now, we'll check for chapters from the last week
                since_date = datetime.utcnow() - timedelta(days=7)
                
                source_new_chapters = await source.get_new_chapters(manga.source_id, since_date)
                
                async for db in get_async_db():
                    # Check which chapters are new compared to what's in the database
                    for chapter in source_new_chapters:
                        existing_chapter = await ChapterRepository.get_by_manga_and_number(db, manga.id, chapter.chapter_number)
                        if not existing_chapter:
                            # Mark chapter as new
                            new_chapters.append(chapter)
                            
                            # Save new chapter to database
                            chapter_data = {
                                'manga_id': manga.id,
                                'chapter_number': chapter.chapter_number,
                                'title': chapter.title or f"Chapter {chapter.chapter_number}",
                                'source_url': chapter.source_url,
                                'is_processed': False
                            }
                            await ChapterRepository.create(db, chapter_data)
            except Exception as e:
                print(f"Error checking new chapters for manga {manga.source_id}: {e}")
        
        return new_chapters
    
    async def get_processable_chapters(self) -> list[ChapterInfo]:
        """Get chapters that are ready to be processed (not yet processed)."""
        processable_chapters = []

        async for db in get_async_db():
            # Get chapters that haven't been processed yet
            db_chapters = await ChapterRepository.get_unprocessed_chapters(db)

            for db_chapter in db_chapters:
                # Convert DB Chapter object to ChapterInfo
                chapter_info = ChapterInfo(
                    chapter_number=db_chapter.chapter_number,
                    source_url=db_chapter.source_url,
                    title=db_chapter.title,
                    published_at=db_chapter.created_at
                )
                processable_chapters.append(chapter_info)

        return processable_chapters
    
    async def close(self):
        """Close all source connections."""
        for source in self.sources.values():
            if hasattr(source, 'close'):
                await source.close()
    
    def _deduplicate_manga(self, manga_list: list[MangaInfo]) -> list[MangaInfo]:
        """Deduplicate manga based on title similarity."""
        if not manga_list:
            return []
        
        unique_manga = [manga_list[0]]  # Always keep the first item
        
        for manga in manga_list[1:]:
            is_duplicate = False
            
            for existing_manga in unique_manga:
                # Calculate similarity between titles
                similarity = SequenceMatcher(None, manga.title.lower(), existing_manga.title.lower()).ratio()
                
                # If similarity is above 80%, consider it a duplicate
                if similarity > 0.8:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_manga.append(manga)
        
        return unique_manga


# Global instance for convenience
discovery_manager = DiscoveryManager()