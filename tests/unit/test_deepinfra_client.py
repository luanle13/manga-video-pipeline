"""Tests for DeepInfra API client."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.scriptgen.deepinfra_client import (
    DeepInfraAPIError,
    DeepInfraClient,
)


@pytest.fixture
def client() -> DeepInfraClient:
    """Create a DeepInfra client for testing."""
    return DeepInfraClient(
        api_key="test-api-key",
        base_url="https://api.deepinfra.com/v1/openai",
        model="Qwen/Qwen2.5-72B-Instruct",
    )


@pytest.fixture
def sample_api_response() -> dict:
    """Sample successful API response."""
    return {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "Qwen/Qwen2.5-72B-Instruct",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Đây là một câu chuyện phiêu lưu tuyệt vời về One Piece.",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 150,
            "completion_tokens": 200,
            "total_tokens": 350,
        },
    }


@pytest.fixture
def sample_manga_info() -> dict:
    """Sample manga information."""
    return {
        "title": "One Piece",
        "description": "A pirate adventure story",
        "genres": ["Action", "Adventure"],
    }


@pytest.fixture
def sample_chapter_info() -> dict:
    """Sample chapter information."""
    return {
        "chapter_number": "1",
        "title": "Romance Dawn",
        "page_count": 54,
    }


class TestClientInitialization:
    """Tests for client initialization."""

    def test_client_initializes_with_correct_params(self) -> None:
        """Test that client initializes with correct parameters."""
        client = DeepInfraClient(
            api_key="my-api-key",
            base_url="https://api.deepinfra.com/v1/openai",
            model="Qwen/Qwen2.5-72B-Instruct",
        )

        assert client._api_key == "my-api-key"
        assert client._base_url == "https://api.deepinfra.com/v1/openai"
        assert client._model == "Qwen/Qwen2.5-72B-Instruct"

    def test_client_strips_trailing_slash_from_base_url(self) -> None:
        """Test that trailing slash is removed from base URL."""
        client = DeepInfraClient(
            api_key="test-key",
            base_url="https://api.deepinfra.com/v1/openai/",
        )

        assert client._base_url == "https://api.deepinfra.com/v1/openai"

    def test_client_uses_default_model(self) -> None:
        """Test that default model is used when not specified."""
        client = DeepInfraClient(
            api_key="test-key",
            base_url="https://api.deepinfra.com/v1/openai",
        )

        assert client._model == "Qwen/Qwen2.5-72B-Instruct"

    def test_api_key_not_logged(self, caplog) -> None:
        """Test that API key is never logged."""
        DeepInfraClient(
            api_key="secret-api-key",
            base_url="https://api.deepinfra.com/v1/openai",
        )

        # Check that API key doesn't appear in logs
        for record in caplog.records:
            assert "secret-api-key" not in record.getMessage()
            assert "secret-api-key" not in str(record.__dict__)


class TestGenerateText:
    """Tests for generate_text method."""

    def test_generate_text_returns_content(
        self, client: DeepInfraClient, sample_api_response: dict
    ) -> None:
        """Test that generate_text returns assistant message content."""
        with patch.object(client._client, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = sample_api_response
            mock_post.return_value = mock_resp

            result = client.generate_text(
                system_prompt="You are a helpful assistant.",
                user_prompt="Tell me about One Piece",
                max_tokens=4096,
                temperature=0.7,
            )

        assert result == "Đây là một câu chuyện phiêu lưu tuyệt vời về One Piece."

    def test_generate_text_uses_correct_request_structure(
        self, client: DeepInfraClient, sample_api_response: dict
    ) -> None:
        """Test that API request has correct structure."""
        with patch.object(client._client, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = sample_api_response
            mock_post.return_value = mock_resp

            client.generate_text(
                system_prompt="You are a helpful assistant.",
                user_prompt="Tell me about One Piece",
                max_tokens=2048,
                temperature=0.5,
            )

        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Check URL
        assert call_args[0][0] == "https://api.deepinfra.com/v1/openai/chat/completions"

        # Check payload
        payload = call_args.kwargs["json"]
        assert payload["model"] == "Qwen/Qwen2.5-72B-Instruct"
        assert payload["max_tokens"] == 2048
        assert payload["temperature"] == 0.5
        assert len(payload["messages"]) == 2
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][0]["content"] == "You are a helpful assistant."
        assert payload["messages"][1]["role"] == "user"
        assert payload["messages"][1]["content"] == "Tell me about One Piece"

    def test_generate_text_handles_usage_data(
        self, client: DeepInfraClient, sample_api_response: dict
    ) -> None:
        """Test that API responses with usage data are handled correctly."""
        with patch.object(client._client, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = sample_api_response
            mock_post.return_value = mock_resp

            result = client.generate_text(
                system_prompt="System",
                user_prompt="User",
            )

        # Verify the response was processed correctly
        assert result == "Đây là một câu chuyện phiêu lưu tuyệt vời về One Piece."

    def test_generate_text_measures_latency(
        self, client: DeepInfraClient, sample_api_response: dict
    ) -> None:
        """Test that API latency is measured correctly."""
        with patch.object(client._client, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = sample_api_response
            mock_post.return_value = mock_resp

            with patch("src.scriptgen.deepinfra_client.time.time") as mock_time:
                mock_time.side_effect = [0, 1.5]  # Start and end time
                result = client.generate_text("System", "User")

        # Verify the call completed successfully
        assert result == "Đây là một câu chuyện phiêu lưu tuyệt vời về One Piece."
        # Verify time.time was called twice (start and end)
        assert mock_time.call_count == 2

    def test_generate_text_raises_on_empty_content(
        self, client: DeepInfraClient
    ) -> None:
        """Test that empty content raises error."""
        response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                    }
                }
            ],
            "usage": {},
        }

        with patch.object(client._client, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = response
            mock_post.return_value = mock_resp

            with pytest.raises(DeepInfraAPIError, match="Empty content"):
                client.generate_text("System", "User")

    def test_generate_text_raises_on_no_choices(
        self, client: DeepInfraClient
    ) -> None:
        """Test that missing choices raises error."""
        response = {
            "choices": [],
            "usage": {},
        }

        with patch.object(client._client, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = response
            mock_post.return_value = mock_resp

            with pytest.raises(DeepInfraAPIError, match="No choices"):
                client.generate_text("System", "User")


class TestRetryLogic:
    """Tests for retry logic."""

    def test_retry_on_429_response(
        self, client: DeepInfraClient, sample_api_response: dict
    ) -> None:
        """Test that 429 responses trigger retry."""
        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            if call_count < 3:
                mock_resp.status_code = 429
                mock_resp.text = "Rate limit exceeded"
            else:
                mock_resp.status_code = 200
                mock_resp.json.return_value = sample_api_response
            return mock_resp

        with patch.object(client._client, "post", side_effect=mock_post):
            with patch("src.scriptgen.deepinfra_client.time.sleep"):
                result = client.generate_text("System", "User")

        assert call_count == 3
        assert result == "Đây là một câu chuyện phiêu lưu tuyệt vời về One Piece."

    def test_retry_on_500_response(
        self, client: DeepInfraClient, sample_api_response: dict
    ) -> None:
        """Test that 500 responses trigger retry."""
        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            if call_count < 2:
                mock_resp.status_code = 500
                mock_resp.text = "Internal server error"
            else:
                mock_resp.status_code = 200
                mock_resp.json.return_value = sample_api_response
            return mock_resp

        with patch.object(client._client, "post", side_effect=mock_post):
            with patch("src.scriptgen.deepinfra_client.time.sleep"):
                result = client.generate_text("System", "User")

        assert call_count == 2
        assert "tuyệt vời" in result

    def test_retry_on_502_response(
        self, client: DeepInfraClient, sample_api_response: dict
    ) -> None:
        """Test that 502 responses trigger retry."""
        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            if call_count < 2:
                mock_resp.status_code = 502
                mock_resp.text = "Bad gateway"
            else:
                mock_resp.status_code = 200
                mock_resp.json.return_value = sample_api_response
            return mock_resp

        with patch.object(client._client, "post", side_effect=mock_post):
            with patch("src.scriptgen.deepinfra_client.time.sleep"):
                result = client.generate_text("System", "User")

        assert call_count == 2
        assert result

    def test_retry_on_503_response(
        self, client: DeepInfraClient, sample_api_response: dict
    ) -> None:
        """Test that 503 responses trigger retry."""
        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            if call_count < 2:
                mock_resp.status_code = 503
                mock_resp.text = "Service unavailable"
            else:
                mock_resp.status_code = 200
                mock_resp.json.return_value = sample_api_response
            return mock_resp

        with patch.object(client._client, "post", side_effect=mock_post):
            with patch("src.scriptgen.deepinfra_client.time.sleep"):
                result = client.generate_text("System", "User")

        assert call_count == 2
        assert result

    def test_max_retries_exceeded_raises_error(self, client: DeepInfraClient) -> None:
        """Test that max retries exceeded raises error."""
        with patch.object(client._client, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_resp.text = "Internal server error"
            mock_post.return_value = mock_resp

            with patch("src.scriptgen.deepinfra_client.time.sleep"):
                with pytest.raises(DeepInfraAPIError) as exc_info:
                    client.generate_text("System", "User")

        assert exc_info.value.status_code == 500

    def test_exponential_backoff_delays(self, client: DeepInfraClient) -> None:
        """Test that exponential backoff is used for delays."""
        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            mock_resp.status_code = 429
            mock_resp.text = "Rate limit"
            return mock_resp

        with patch.object(client._client, "post", side_effect=mock_post):
            with patch("src.scriptgen.deepinfra_client.time.sleep") as mock_sleep:
                with pytest.raises(DeepInfraAPIError):
                    client.generate_text("System", "User")

        # Check that sleep was called with exponential backoff
        # First retry: 2 * 2^0 = 2 seconds
        # Second retry: 2 * 2^1 = 4 seconds
        assert mock_sleep.call_count == 2
        assert mock_sleep.call_args_list[0][0][0] == 2
        assert mock_sleep.call_args_list[1][0][0] == 4

    def test_non_retryable_error_raises_immediately(
        self, client: DeepInfraClient
    ) -> None:
        """Test that non-retryable errors (like 400) don't trigger retry."""
        with patch.object(client._client, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 400
            mock_resp.text = "Bad request"
            mock_post.return_value = mock_resp

            with pytest.raises(DeepInfraAPIError) as exc_info:
                client.generate_text("System", "User")

        # Should only call once (no retries)
        assert mock_post.call_count == 1
        assert exc_info.value.status_code == 400


class TestTimeoutHandling:
    """Tests for timeout handling."""

    def test_timeout_triggers_retry(
        self, client: DeepInfraClient, sample_api_response: dict
    ) -> None:
        """Test that timeout triggers retry."""
        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.TimeoutException("Request timeout")
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = sample_api_response
            return mock_resp

        with patch.object(client._client, "post", side_effect=mock_post):
            with patch("src.scriptgen.deepinfra_client.time.sleep"):
                result = client.generate_text("System", "User")

        assert call_count == 3
        assert result

    def test_timeout_after_all_retries_raises(self, client: DeepInfraClient) -> None:
        """Test that timeout after all retries raises exception."""
        with patch.object(client._client, "post") as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Request timeout")

            with patch("src.scriptgen.deepinfra_client.time.sleep"):
                with pytest.raises(httpx.TimeoutException):
                    client.generate_text("System", "User")

        # Should try MAX_RETRIES times
        assert mock_post.call_count == 3


class TestGenerateScriptSegment:
    """Tests for generate_script_segment method."""

    def test_generate_script_includes_tone_and_style(
        self,
        client: DeepInfraClient,
        sample_manga_info: dict,
        sample_chapter_info: dict,
        sample_api_response: dict,
    ) -> None:
        """Test that system prompt includes tone and style."""
        with patch.object(client._client, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = sample_api_response
            mock_post.return_value = mock_resp

            client.generate_script_segment(
                manga_info=sample_manga_info,
                chapter_info=sample_chapter_info,
                tone="exciting",
                style="energetic",
            )

        # Verify the request
        call_args = mock_post.call_args
        payload = call_args.kwargs["json"]
        system_message = payload["messages"][0]["content"]

        assert "Vietnamese manga reviewer" in system_message
        assert "Vietnamese" in system_message
        assert "exciting" in system_message
        assert "energetic" in system_message

    def test_generate_script_includes_manga_context(
        self,
        client: DeepInfraClient,
        sample_manga_info: dict,
        sample_chapter_info: dict,
        sample_api_response: dict,
    ) -> None:
        """Test that user prompt includes manga and chapter context."""
        with patch.object(client._client, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = sample_api_response
            mock_post.return_value = mock_resp

            client.generate_script_segment(
                manga_info=sample_manga_info,
                chapter_info=sample_chapter_info,
                tone="dramatic",
                style="formal",
            )

        # Verify the request
        call_args = mock_post.call_args
        payload = call_args.kwargs["json"]
        user_message = payload["messages"][1]["content"]

        assert "One Piece" in user_message
        assert "Action" in user_message
        assert "Adventure" in user_message
        assert "Romance Dawn" in user_message
        assert "54" in user_message  # page count

    def test_generate_script_returns_text(
        self,
        client: DeepInfraClient,
        sample_manga_info: dict,
        sample_chapter_info: dict,
        sample_api_response: dict,
    ) -> None:
        """Test that generate_script_segment returns Vietnamese text."""
        with patch.object(client._client, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = sample_api_response
            mock_post.return_value = mock_resp

            result = client.generate_script_segment(
                manga_info=sample_manga_info,
                chapter_info=sample_chapter_info,
                tone="comedic",
                style="casual",
            )

        assert result == "Đây là một câu chuyện phiêu lưu tuyệt vời về One Piece."

    def test_generate_script_completes_successfully(
        self,
        client: DeepInfraClient,
        sample_manga_info: dict,
        sample_chapter_info: dict,
        sample_api_response: dict,
    ) -> None:
        """Test that script generation completes successfully."""
        with patch.object(client._client, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = sample_api_response
            mock_post.return_value = mock_resp

            result = client.generate_script_segment(
                manga_info=sample_manga_info,
                chapter_info=sample_chapter_info,
                tone="exciting",
                style="energetic",
            )

        # Verify script was generated
        assert result == "Đây là một câu chuyện phiêu lưu tuyệt vời về One Piece."
        assert isinstance(result, str)
        assert len(result) > 0


class TestClientLifecycle:
    """Tests for client lifecycle management."""

    def test_context_manager(self) -> None:
        """Test client works as context manager."""
        with DeepInfraClient(
            api_key="test-key",
            base_url="https://api.deepinfra.com/v1/openai",
        ) as client:
            assert client._client is not None

    def test_close_method(self) -> None:
        """Test close method closes HTTP client."""
        client = DeepInfraClient(
            api_key="test-key",
            base_url="https://api.deepinfra.com/v1/openai",
        )
        with patch.object(client._client, "close") as mock_close:
            client.close()
            mock_close.assert_called_once()
