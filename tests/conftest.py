import pytest
import pytest_asyncio
import aiosqlite
import tempfile
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
from io import BytesIO


@pytest_asyncio.fixture(scope="session")
async def test_db():
    """Create an in-memory SQLite database for testing."""
    async with aiosqlite.connect(":memory:") as db:
        # Create tables for testing if needed
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id INTEGER PRIMARY KEY,
                manga_title TEXT,
                chapter_number REAL,
                language TEXT,
                status TEXT,
                task_id TEXT,
                error_message TEXT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS uploads (
                id INTEGER PRIMARY KEY,
                video_path TEXT,
                platform TEXT,
                status TEXT,
                upload_id TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
        yield db


@pytest_asyncio.fixture
async def repository(test_db):
    """Create a repository for testing."""
    from src.db import get_db_session, PipelineRun
    # Create a mock repository for testing
    class MockRepository:
        def __init__(self, db):
            self.db = db
        
        async def get_pipeline_run(self, run_id: int):
            async with self.db.execute("SELECT * FROM pipeline_runs WHERE id = ?", (run_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "id": row[0],
                        "manga_title": row[1],
                        "chapter_number": row[2],
                        "language": row[3],
                        "status": row[4],
                        "task_id": row[5],
                        "error_message": row[6],
                        "started_at": row[7],
                        "completed_at": row[8]
                    }
                return None
        
        async def create_pipeline_run(self, manga_title: str, chapter_number: float, language: str, status: str):
            async with self.db.execute(
                "INSERT INTO pipeline_runs (manga_title, chapter_number, language, status) VALUES (?, ?, ?, ?)",
                (manga_title, chapter_number, language, status)
            ) as cursor:
                await self.db.commit()
                return cursor.lastrowid
    
    repo = MockRepository(test_db)
    yield repo


@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI client for testing."""
    with patch("openai.AsyncOpenAI") as mock_client:
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create = AsyncMock()
        mock_client_instance.audio.speech.create = AsyncMock()
        mock_client.return_value = mock_client_instance
        yield mock_client_instance


@pytest_asyncio.fixture
async def sample_images():
    """Create temporary image files for testing."""
    temp_dir = Path(tempfile.mkdtemp())
    
    # Create mock image files
    images = []
    for i in range(5):
        img_path = temp_dir / f"test_image_{i}.jpg"
        # Create a minimal JPEG file for testing
        with open(img_path, "wb") as f:
            # Write a minimal JPEG file header
            f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00')
            f.write(b'\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f')
            f.write(b'\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(c\x1c\x1c\x1c\xff\xc0\x00\x11\x08\x00\x01')
            f.write(b'\x00\x01\x03\x01"\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00')
            f.write(b'\x00\x00\x00\x00\x00\x00\x00\x00\x08\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00')
            f.write(b'\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xd2\xcf \xff\xd9')
        images.append(img_path)
    
    yield images
    
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest_asyncio.fixture
async def sample_audio():
    """Create a temporary audio file for testing."""
    temp_dir = Path(tempfile.mkdtemp())
    audio_path = temp_dir / "test_audio.mp3"
    
    # Create a minimal MP3 file for testing
    with open(audio_path, "wb") as f:
        # Write a minimal valid MP3 header
        f.write(b'\x49\x44\x33\x03\x00\x00\x00\x00\x00\x00')  # ID3 header
        f.write(b'\xff\xfb\x90\x00')  # MP3 frame header
    
    yield audio_path
    
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_httpx():
    """Create a mock HTTPX client for testing."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(return_value={"test": "data"})
        mock_client.get.return_value = mock_response
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client_class.return_value.__aexit__.return_value = None
        yield mock_client


@pytest.fixture
def mock_playwright():
    """Create a mock Playwright browser for testing."""
    with patch("playwright.async_api.Playwright") as mock_playwright:
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.chromium.launch.return_value = mock_browser
        
        yield {
            'playwright': mock_playwright,
            'browser': mock_browser,
            'context': mock_context,
            'page': mock_page
        }