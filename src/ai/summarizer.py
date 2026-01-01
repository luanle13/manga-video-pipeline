from __future__ import annotations
import asyncio
import base64
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import List, Union
import time

from openai import AsyncOpenAI
import openai


@dataclass(slots=True)
class SummaryResult:
    """Result of manga chapter summarization."""
    script: str
    word_count: int
    estimated_duration: int  # in seconds


class MangaSummarizer:
    """Summarizes manga chapters using OpenAI's GPT-4o-mini with vision capabilities."""
    
    def __init__(self, api_key: str | None = None):
        """
        Initialize the MangaSummarizer.
        
        Args:
            api_key: OpenAI API key. If None, will be read from environment variables.
        """
        self.client = AsyncOpenAI(api_key=api_key)
        
    def _encode_image(self, image_path: Path) -> str:
        """Encode an image to base64 string.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Base64 encoded string of the image
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def _select_key_images(self, images: List[Path], max_images: int = 12) -> List[Path]:
        """Select a maximum number of key images from the list.
        
        Args:
            images: List of image paths
            max_images: Maximum number of images to select
            
        Returns:
            List of selected image paths
        """
        if len(images) <= max_images:
            return images
        
        # Select evenly spaced images
        step = len(images) // max_images
        selected_images = [images[i] for i in range(0, len(images), step)]
        
        # Ensure we include the last image if it's not already included
        if len(selected_images) < max_images and images[-1] not in selected_images:
            selected_images = selected_images[:-1] + [images[-1]]
            
        return selected_images[:max_images]
    
    async def _call_openai_vision_api(
        self,
        images: List[Path],
        manga_title: str,
        chapter_number: float,
        language: str,
        target_duration: int
    ) -> str:
        """Call the OpenAI vision API to generate a summary.
        
        Args:
            images: List of image paths to analyze
            manga_title: Title of the manga
            chapter_number: Chapter number
            language: Language code ("en" or "vn")
            target_duration: Target duration in seconds
            
        Returns:
            Generated script as a string
        """
        # Encode images to base64
        encoded_images = [self._encode_image(img) for img in images]
        
        # Define language-specific instructions
        if language == "vn":
            instruction = f"""
Bạn là một narrator tài năng, hãy tạo một kịch bản hấp dẫn cho video YouTube Shorts dài {target_duration} giây 
về chương {chapter_number} của manga '{manga_title}'. Kịch bản nên hấp dẫn, súc tích và phù hợp với định dạng video ngắn. 
Chỉ trả về kịch bản, không có phần mở đầu hay giải thích bổ sung.
"""
        else:  # Default to English
            instruction = f"""
You are a skilled narrator, create an engaging script for a {target_duration}-second YouTube Shorts video
about chapter {chapter_number} of the manga '{manga_title}'. The script should be captivating, concise, and suitable 
for short-form video content. Return only the script, no additional introductions or explanations.
"""
        
        # Prepare message content with images
        message_content = [
            {"type": "text", "text": instruction}
        ]
        
        for encoded_img in encoded_images:
            message_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{encoded_img}",
                    "detail": "high"
                }
            })
        
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
                            "content": message_content
                        }
                    ],
                    max_tokens=1000,
                    temperature=0.7
                )
                
                return response.choices[0].message.content.strip()
                
            except openai.RateLimitError:
                if attempt < max_retries - 1:
                    logging.warning(f"Rate limit hit, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    raise
            except openai.APIConnectionError:
                if attempt < max_retries - 1:
                    logging.warning(f"API connection error, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    raise
            except Exception as e:
                if attempt < max_retries - 1:
                    logging.warning(f"API error: {str(e)}, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    raise
        
        raise Exception("Failed to get response from OpenAI API after retries")
    
    async def summarize_chapter(
        self,
        images: List[Path],
        manga_title: str,
        chapter_number: float,
        language: str,
        target_duration: int = 60
    ) -> SummaryResult:
        """
        Summarize a manga chapter based on the provided images.
        
        Args:
            images: List of manga page images (Path objects)
            manga_title: Title of the manga
            chapter_number: Chapter number
            language: Language code ("en" or "vn")
            target_duration: Target duration in seconds (default 60)
            
        Returns:
            SummaryResult object containing the script, word count, and estimated duration
        """
        # Validate language
        if language not in ["en", "vn"]:
            raise ValueError(f"Unsupported language: {language}. Supported languages are 'en' and 'vn'.")
        
        # Select key images if there are too many
        selected_images = self._select_key_images(images)
        
        # Generate the script using OpenAI
        script = await self._call_openai_vision_api(
            selected_images,
            manga_title,
            chapter_number,
            language,
            target_duration
        )
        
        # Calculate word count and estimated duration
        word_count = len(script.split())
        # Assuming average speaking rate of 150 words per minute
        estimated_duration = int((word_count / 150) * 60)
        
        return SummaryResult(
            script=script,
            word_count=word_count,
            estimated_duration=estimated_duration
        )


# For backward compatibility or synchronous use
def summarize_chapter(
    images: List[Path],
    manga_title: str,
    chapter_number: float,
    language: str,
    target_duration: int = 60
) -> SummaryResult:
    """Synchronous version of the summarize_chapter method."""
    import os

    api_key = os.getenv("OPENAI_API_KEY")
    summarizer = MangaSummarizer(api_key=api_key)

    # Run the async function in a new event loop
    try:
        # Check if already in an event loop
        loop = asyncio.get_running_loop()

        # If already in an event loop, we need to run in a separate thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(
                lambda: asyncio.run(
                    summarizer.summarize_chapter(
                        images, manga_title, chapter_number, language, target_duration
                    )
                )
            )
            return future.result()
    except RuntimeError:
        # No event loop running, safe to use asyncio.run
        return asyncio.run(summarizer.summarize_chapter(
            images, manga_title, chapter_number, language, target_duration
        ))