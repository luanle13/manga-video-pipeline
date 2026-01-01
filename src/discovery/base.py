from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class MangaInfo:
    """Data class for manga information."""
    source: str
    source_id: str  # ID from the source platform (e.g., manga ID in MangaDex)
    title: str
    cover_url: str | None = None
    trending_rank: int | None = None
    genres: list[str] | None = None
    
    def __post_init__(self):
        if self.genres is None:
            self.genres = []


@dataclass(slots=True)
class ChapterInfo:
    """Data class for chapter information."""
    chapter_number: float
    source_url: str
    title: str | None = None
    published_at: datetime | None = None


class DiscoverySource(ABC):
    """Abstract base class for manga discovery sources."""
    
    @abstractmethod
    async def get_trending(self, limit: int = 20) -> list[MangaInfo]:
        """Get trending manga from the source."""
        pass
    
    @abstractmethod
    async def get_chapters(self, manga_id: str) -> list[ChapterInfo]:
        """Get all chapters for a specific manga."""
        pass
    
    @abstractmethod
    async def get_new_chapters(self, manga_id: str, since: datetime) -> list[ChapterInfo]:
        """Get new chapters for a specific manga since a given date."""
        pass