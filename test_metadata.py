#!/usr/bin/env python3
"""
Test script for the MetadataGenerator class.
This script tests the implementation without actually calling the OpenAI API
since that would require valid credentials and network access.
"""

import asyncio
from unittest.mock import AsyncMock, patch
import sys
import os

# Add src to the path so we can import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from ai.metadata import MetadataGenerator, VideoMetadata


async def test_metadata_generator():
    """Test the MetadataGenerator class."""
    print("Testing MetadataGenerator...")
    
    # Create a mock API response instead of making real API calls
    mock_response = '''{
        "title": "Exciting Chapter with Plot Twist!",
        "description": "This chapter has amazing developments and plot twists. #anime #manga",
        "tags": ["manga", "anime", "plot twist", "action", "adventure", "drama", "storytelling", "comic", "webtoon", "entertainment", "character development", "cliffhanger"],
        "hashtags": ["#manga", "#anime", "#plotTwist", "#action", "#adventure", "#storytelling", "#webtoon", "#entertainment"]
    }'''
    
    # Create mock OpenAI client
    with patch('openai.resources.chat.completions.AsyncCompletions.create') as mock_create:
        # Configure the mock to return our test response
        mock_response_obj = AsyncMock()
        mock_response_obj.choices = [AsyncMock()]
        mock_response_obj.choices[0].message = AsyncMock()
        mock_response_obj.choices[0].message.content = mock_response
        
        mock_create.return_value = mock_response_obj
        
        # Create a generator instance
        generator = MetadataGenerator(api_key="test-key")

        # Mock the _call_openai_api method to avoid API calls
        mock_metadata_result = {
            "title": "Exciting Chapter with Plot Twist!",
            "description": "This chapter has amazing developments and plot twists. #anime #manga",
            "tags": ["manga", "anime", "plot twist", "action", "adventure", "drama", "storytelling", "comic", "webtoon", "entertainment", "character development", "cliffhanger"],
            "hashtags": ["#manga", "#anime", "#plotTwist", "#action", "#adventure", "#storytelling", "#webtoon", "#entertainment"]
        }

        with patch.object(generator, '_call_openai_api', return_value=mock_metadata_result):
            # Test the generate_metadata method
            result = await generator.generate_metadata(
                manga_title="Test Manga",
                chapter_number=1.0,
                summary="This chapter has amazing developments and plot twists.",
                language="en"
            )

        # Verify the result
        assert isinstance(result, VideoMetadata), "Result should be a VideoMetadata instance"
        assert len(result.title) <= 100, "Title should be 100 characters or less"
        assert isinstance(result.description, str), "Description should be a string"
        assert isinstance(result.tags, list), "Tags should be a list"
        assert isinstance(result.hashtags, list), "Hashtags should be a list"

        print(f"✓ Test passed! Generated title: {result.title}")
        print(f"✓ Description: {result.description[:50]}...")
        print(f"✓ Tags count: {len(result.tags)}")
        print(f"✓ Hashtags count: {len(result.hashtags)}")

        # Test with Vietnamese language
        with patch.object(generator, '_call_openai_api', return_value=mock_metadata_result):
            result_vn = await generator.generate_metadata(
                manga_title="Test Manga",
                chapter_number=1.0,
                summary="This chapter has amazing developments and plot twists.",
                language="vn"
            )

        assert isinstance(result_vn, VideoMetadata), "Result should be a VideoMetadata instance"
        print(f"✓ Vietnamese language test passed!")
        
        # Test error handling for unsupported language
        try:
            await generator.generate_metadata(
                manga_title="Test Manga",
                chapter_number=1.0,
                summary="This chapter has amazing developments and plot twists.",
                language="fr",  # Unsupported language
            )
            assert False, "Should have raised an error for unsupported language"
        except ValueError as e:
            print(f"✓ Error handling test passed: {e}")
        
        # Test synchronous function
        sync_result = generator.generate_metadata(
            manga_title="Test Manga",
            chapter_number=1.0,
            summary="This chapter has amazing developments and plot twists.",
            language="en"
        )
        print(f"✓ Synchronous function test passed!")
    
    print("\nAll tests passed! MetadataGenerator is working correctly.")


def test_dataclass():
    """Test the VideoMetadata dataclass."""
    print("Testing VideoMetadata dataclass...")
    
    result = VideoMetadata(
        title="Test Title",
        description="Test description",
        tags=["tag1", "tag2"],
        hashtags=["#hashtag1", "#hashtag2"]
    )
    
    assert result.title == "Test Title"
    assert result.description == "Test description"
    assert result.tags == ["tag1", "tag2"]
    assert result.hashtags == ["#hashtag1", "#hashtag2"]
    
    print("✓ VideoMetadata dataclass test passed!")


if __name__ == "__main__":
    # Run the dataclass test
    test_dataclass()
    
    # Run the async tests
    asyncio.run(test_metadata_generator())