from __future__ import annotations
import asyncio
from dataclasses import dataclass
import json
import logging
from typing import List

from openai import AsyncOpenAI


@dataclass(slots=True)
class VideoMetadata:
    """Video metadata for social media platforms."""
    title: str
    description: str
    tags: List[str]
    hashtags: List[str]


class MetadataGenerator:
    """Generates metadata for manga chapter videos optimized for social media discoverability."""
    
    def __init__(self, api_key: str | None = None):
        """
        Initialize the MetadataGenerator.
        
        Args:
            api_key: OpenAI API key. If None, will be read from environment variables.
        """
        self.client = AsyncOpenAI(api_key=api_key)
    
    async def _call_openai_api(self, manga_title: str, chapter_number: float, summary: str, language: str) -> dict:
        """Call the OpenAI API to generate metadata.
        
        Args:
            manga_title: Title of the manga
            chapter_number: Chapter number
            summary: Summary of the chapter
            language: Language ("en" or "vn")
            
        Returns:
            Dictionary containing title, description, tags, and hashtags
        """
        # Define language-specific prompts
        if language == "vn":
            prompt = f"""
Bạn là một chuyên gia về tiếp thị nội dung trên mạng xã hội. Hãy tạo metadata cho video manga 
ngắn (YouTube Shorts, TikTok, Reels) của manga '{manga_title}' chương {chapter_number}.
Dưới đây là tóm tắt chương: {summary}

Hãy trả về JSON với các trường sau:
- "title": tiêu đề hấp dẫn, tối đa 100 ký tự, thu hút người xem
- "description": mô tả nội dung video, thêm hashtag vào cuối mô tả
- "tags": danh sách 10-15 tag liên quan từ khóa chính, thể loại, nhân vật
- "hashtags": danh sách các hashtag phổ biến, trend, phù hợp với nội dung

Chỉ trả về JSON, không có lời dẫn hay giải thích thêm.
"""
        else:  # Default to English
            prompt = f"""
You are a social media content marketing expert. Generate metadata for a short-form video 
(YouTube Shorts, TikTok, Reels) of manga '{manga_title}' chapter {chapter_number}.
Here is the chapter summary: {summary}

Return a JSON with the following fields:
- "title": catchy, engaging title, maximum 100 characters, attention-grabbing
- "description": description of the video content, add hashtags at the end
- "tags": list of 10-15 relevant tags from main keywords, genre, characters
- "hashtags": list of trending, popular hashtags appropriate for the content

Return only the JSON, no additional text or explanations.
"""
        
        # Call the OpenAI API with retry logic
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    max_tokens=2000,
                    temperature=0.7,
                    response_format={"type": "json_object"}
                )
                
                # Parse the JSON response
                response_text = response.choices[0].message.content.strip()
                
                # Clean up response if needed (remove any markdown formatting)
                if response_text.startswith("```json"):
                    response_text = response_text[7:]  # Remove ```json
                if response_text.endswith("```"):
                    response_text = response_text[:-3]  # Remove ```
                
                # Parse the JSON
                metadata = json.loads(response_text)
                
                return metadata
                
            except Exception as e:
                if attempt < max_retries - 1:
                    logging.warning(f"API error: {str(e)}, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    raise
        
        raise Exception("Failed to get response from OpenAI API after retries")
    
    async def generate_metadata(
        self,
        manga_title: str,
        chapter_number: float,
        summary: str,
        language: str
    ) -> VideoMetadata:
        """
        Generate metadata for a manga chapter video.
        
        Args:
            manga_title: Title of the manga
            chapter_number: Chapter number
            summary: Chapter summary to base metadata on
            language: Language code ("en" or "vn")
            
        Returns:
            VideoMetadata object with title, description, tags, and hashtags
        """
        # Validate language
        if language not in ["en", "vn"]:
            raise ValueError(f"Unsupported language: {language}. Supported languages are 'en' and 'vn'.")
        
        # Generate the metadata using OpenAI
        metadata = await self._call_openai_api(manga_title, chapter_number, summary, language)
        
        # Ensure title is within character limit
        title = metadata.get('title', '')[:100]
        
        # Get other fields, providing defaults if not present
        description = metadata.get('description', '')
        tags = metadata.get('tags', [])
        hashtags = metadata.get('hashtags', [])
        
        # Ensure we have proper lists for tags and hashtags
        if not isinstance(tags, list):
            tags = []
        if not isinstance(hashtags, list):
            hashtags = []
        
        return VideoMetadata(
            title=title,
            description=description,
            tags=tags,
            hashtags=hashtags
        )


# For backward compatibility or synchronous use
def generate_metadata(
    manga_title: str,
    chapter_number: float,
    summary: str,
    language: str
) -> VideoMetadata:
    """Synchronous version of the generate_metadata method."""
    import os
    
    api_key = os.getenv("OPENAI_API_KEY")
    generator = MetadataGenerator(api_key=api_key)
    
    # Run the async function in a new event loop
    try:
        loop = asyncio.get_running_loop()
        
        # If already in an event loop, we need to run in a separate thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(
                lambda: asyncio.run(
                    generator.generate_metadata(
                        manga_title, chapter_number, summary, language
                    )
                )
            )
            return future.result()
    except RuntimeError:
        # No event loop running, safe to use asyncio.run
        return asyncio.run(generator.generate_metadata(
            manga_title, chapter_number, summary, language
        ))