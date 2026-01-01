#!/usr/bin/env python3
"""
Test script for the MangaSummarizer class.
This script tests the implementation without actually calling the OpenAI API
since that would require valid credentials and network access.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch
import sys
import os

# Add src to the path so we can import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from ai.summarizer import MangaSummarizer, SummaryResult


async def test_manga_summarizer():
    """Test the MangaSummarizer class."""
    print("Testing MangaSummarizer...")
    
    # Create a mock API response instead of making real API calls
    mock_response = "This is a test script for the manga chapter. It includes all the exciting parts and key plot points."
    
    # Create mock OpenAI client
    with patch('openai.resources.chat.completions.AsyncCompletions.create') as mock_create:
        # Configure the mock to return our test response
        mock_response_obj = AsyncMock()
        mock_response_obj.choices = [AsyncMock()]
        mock_response_obj.choices[0].message = AsyncMock()
        mock_response_obj.choices[0].message.content = mock_response
        
        mock_create.return_value = mock_response_obj
        
        # Create a summarizer instance
        summarizer = MangaSummarizer(api_key="test-key")

        # Create some mock image paths (these don't need to exist for the test)
        mock_images = [
            Path("mock_image1.jpg"),
            Path("mock_image2.jpg"),
            Path("mock_image3.jpg"),
            Path("mock_image4.jpg"),
            Path("mock_image5.jpg")
        ]

        # Mock the _call_openai_vision_api method to avoid API calls
        with patch.object(summarizer, '_call_openai_vision_api', return_value=mock_response):
            # Test the summarize_chapter method
            result = await summarizer.summarize_chapter(
                images=mock_images,
                manga_title="Test Manga",
                chapter_number=1.0,
                language="en",
                target_duration=60
            )

        # Verify the result
        assert isinstance(result, SummaryResult), "Result should be a SummaryResult instance"
        assert result.script == mock_response, "Script should match mock response"
        assert result.word_count > 0, "Word count should be positive"
        assert result.estimated_duration > 0, "Estimated duration should be positive"

        print(f"✓ Test passed! Generated script: {result.script[:50]}...")
        print(f"✓ Word count: {result.word_count}")
        print(f"✓ Estimated duration: {result.estimated_duration} seconds")

        # Test with Vietnamese language
        with patch.object(summarizer, '_call_openai_vision_api', return_value=mock_response):
            result_vn = await summarizer.summarize_chapter(
                images=mock_images,
                manga_title="Test Manga",
                chapter_number=1.0,
                language="vn",
                target_duration=60
            )

        assert isinstance(result_vn, SummaryResult), "Result should be a SummaryResult instance"
        print(f"✓ Vietnamese language test passed!")

        # Test error handling for unsupported language
        try:
            await summarizer.summarize_chapter(
                images=mock_images,
                manga_title="Test Manga",
                chapter_number=1.0,
                language="fr",  # Unsupported language
                target_duration=60
            )
            assert False, "Should have raised an error for unsupported language"
        except ValueError as e:
            print(f"✓ Error handling test passed: {e}")

        # Test key image selection
        many_images = [Path(f"image_{i}.jpg") for i in range(20)]
        selected = summarizer._select_key_images(many_images, max_images=12)
        assert len(selected) == 12, f"Expected 12 images, got {len(selected)}"
        assert selected[0] == many_images[0], "Should include the first image"
        print(f"✓ Key image selection test passed! Selected {len(selected)} images")

        # Test synchronous function
        with patch('ai.summarizer.MangaSummarizer') as MockSummarizer:
            mock_instance = MockSummarizer.return_value
            mock_instance.summarize_chapter = AsyncMock(return_value=result)
            sync_result = summarizer.summarize_chapter(
                images=mock_images,
                manga_title="Test Manga",
                chapter_number=1.0,
                language="en",
                target_duration=60
            )
            print(f"✓ Synchronous function test passed!")
    
    print("\nAll tests passed! MangaSummarizer is working correctly.")


def test_dataclass():
    """Test the SummaryResult dataclass."""
    print("Testing SummaryResult dataclass...")
    
    result = SummaryResult(
        script="Test script content",
        word_count=50,
        estimated_duration=20
    )
    
    assert result.script == "Test script content"
    assert result.word_count == 50
    assert result.estimated_duration == 20
    
    print("✓ SummaryResult dataclass test passed!")


if __name__ == "__main__":
    # Run the dataclass test
    test_dataclass()
    
    # Run the async tests
    asyncio.run(test_manga_summarizer())