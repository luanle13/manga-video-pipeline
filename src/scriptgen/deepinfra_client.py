"""DeepInfra API client for Qwen LLM calls."""

import time
from typing import Any

import httpx

from src.common.logging_config import setup_logger

logger = setup_logger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds
DEFAULT_TIMEOUT = 120  # 2 minutes for long generation


class DeepInfraAPIError(Exception):
    """Raised when DeepInfra API returns an error."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class DeepInfraClient:
    """Client for DeepInfra API to interact with Qwen LLM."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str = "Qwen/Qwen2.5-72B-Instruct",
    ) -> None:
        """
        Initialize the DeepInfra client.

        Args:
            api_key: DeepInfra API key for authentication.
            base_url: Base URL for DeepInfra API.
            model: Model name to use (default: Qwen/Qwen2.5-72B-Instruct).
        """
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = httpx.Client(
            timeout=DEFAULT_TIMEOUT,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

        logger.info(
            "DeepInfra client initialized",
            extra={"base_url": self._base_url, "model": model},
        )

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> "DeepInfraClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """
        Generate text using the Qwen LLM via DeepInfra API.

        Args:
            system_prompt: System message to set the context and behavior.
            user_prompt: User message with the actual prompt.
            max_tokens: Maximum number of tokens to generate.
            temperature: Sampling temperature (0.0 to 1.0).

        Returns:
            Generated text content from the assistant.

        Raises:
            DeepInfraAPIError: On API errors.
            httpx.TimeoutException: On timeout.
        """
        url = f"{self._base_url}/chat/completions"
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        start_time = time.time()

        for attempt in range(MAX_RETRIES):
            try:
                logger.debug(
                    "Making DeepInfra API request",
                    extra={
                        "model": self._model,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "attempt": attempt + 1,
                    },
                )

                response = self._client.post(url, json=payload)
                latency = time.time() - start_time

                logger.info(
                    "DeepInfra API response received",
                    extra={"status_code": response.status_code, "latency": latency},
                )

                if response.status_code == 200:
                    response_data = response.json()

                    # Extract token usage if available
                    usage = response_data.get("usage", {})
                    logger.info(
                        "Token usage",
                        extra={
                            "model": self._model,
                            "prompt_tokens": usage.get("prompt_tokens", 0),
                            "completion_tokens": usage.get("completion_tokens", 0),
                            "total_tokens": usage.get("total_tokens", 0),
                            "latency": latency,
                        },
                    )

                    # Extract assistant message content
                    choices = response_data.get("choices", [])
                    if not choices:
                        raise DeepInfraAPIError("No choices in API response")

                    message = choices[0].get("message", {})
                    content = message.get("content", "")

                    if not content:
                        raise DeepInfraAPIError("Empty content in API response")

                    return content

                if response.status_code in (429, 500, 502, 503):
                    # Retry on rate limit or server errors
                    if attempt < MAX_RETRIES - 1:
                        delay = RETRY_BASE_DELAY * (2**attempt)
                        logger.warning(
                            "Retrying after error",
                            extra={
                                "status_code": response.status_code,
                                "attempt": attempt + 1,
                                "delay": delay,
                            },
                        )
                        time.sleep(delay)
                        start_time = time.time()  # Reset timer for next attempt
                        continue

                # Non-retryable error or max retries reached
                error_detail = response.text
                logger.error(
                    "DeepInfra API error",
                    extra={
                        "status_code": response.status_code,
                        "error": error_detail,
                    },
                )
                raise DeepInfraAPIError(
                    f"API request failed: {response.status_code} - {error_detail}",
                    status_code=response.status_code,
                )

            except httpx.TimeoutException:
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2**attempt)
                    logger.warning(
                        "Request timeout, retrying",
                        extra={"url": url, "attempt": attempt + 1, "delay": delay},
                    )
                    time.sleep(delay)
                    start_time = time.time()  # Reset timer for next attempt
                    continue
                logger.error("Request timeout after all retries", extra={"url": url})
                raise

        # Should not reach here, but just in case
        raise DeepInfraAPIError("Max retries exceeded")

    def generate_script_segment(
        self,
        manga_info: dict,
        chapter_info: dict,
        tone: str,
        style: str,
    ) -> str:
        """
        Generate a Vietnamese script segment for a manga chapter.

        Args:
            manga_info: Dictionary containing manga metadata (title, description, genres).
            chapter_info: Dictionary containing chapter metadata (chapter_number, title, page_count).
            tone: Desired tone for the narration (e.g., "exciting", "dramatic", "comedic").
            style: Desired writing style (e.g., "formal", "casual", "energetic").

        Returns:
            Generated Vietnamese script text.

        Raises:
            DeepInfraAPIError: On API errors.
            httpx.TimeoutException: On timeout.
        """
        # Build system prompt
        system_prompt = (
            f"You are a Vietnamese manga reviewer. "
            f"Write in Vietnamese. "
            f"Tone: {tone}. "
            f"Style: {style}."
        )

        # Build user prompt with manga and chapter context
        manga_title = manga_info.get("title", "Unknown")
        manga_description = manga_info.get("description", "")
        manga_genres = manga_info.get("genres", [])
        chapter_number = chapter_info.get("chapter_number", "?")
        chapter_title = chapter_info.get("title", "")
        page_count = chapter_info.get("page_count", 0)

        user_prompt = f"""Create a Vietnamese narration script for this manga chapter:

Manga: {manga_title}
Genres: {", ".join(manga_genres) if manga_genres else "N/A"}
Description: {manga_description}

Chapter: {chapter_number}
Title: {chapter_title}
Page Count: {page_count}

Write an engaging Vietnamese script that introduces this chapter to viewers. Include:
1. A brief hook about the manga
2. Context for this chapter
3. What viewers can expect
4. Maintain the specified tone and style throughout

Keep the script natural and conversational, suitable for video narration."""

        logger.info(
            "Generating script segment",
            extra={
                "manga_title": manga_title,
                "chapter_number": chapter_number,
                "tone": tone,
                "style": style,
            },
        )

        script = self.generate_text(system_prompt, user_prompt)

        logger.info(
            "Script segment generated",
            extra={
                "manga_title": manga_title,
                "chapter_number": chapter_number,
                "script_length": len(script),
            },
        )

        return script
