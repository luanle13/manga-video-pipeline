"""Tests for Edge TTS client."""

import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ttsgen.tts_client import (
    EdgeTTSClient,
    generate_audio_bytes_sync,
    generate_audio_sync,
    get_vietnamese_voices_sync,
)


@pytest.fixture
def tts_client():
    """Create an EdgeTTSClient instance."""
    return EdgeTTSClient(voice_id="vi-VN-HoaiMyNeural")


@pytest.fixture
def sample_vietnamese_voices():
    """Sample Vietnamese voice data."""
    return [
        {
            "ShortName": "vi-VN-HoaiMyNeural",
            "FriendlyName": "Microsoft HoaiMy Online (Natural) - Vietnamese (Vietnam)",
            "Gender": "Female",
            "Locale": "vi-VN",
        },
        {
            "ShortName": "vi-VN-NamMinhNeural",
            "FriendlyName": "Microsoft NamMinh Online (Natural) - Vietnamese (Vietnam)",
            "Gender": "Male",
            "Locale": "vi-VN",
        },
        {
            "ShortName": "en-US-JennyNeural",
            "FriendlyName": "Microsoft Jenny Online (Natural) - English (United States)",
            "Gender": "Female",
            "Locale": "en-US",
        },
    ]


class TestEdgeTTSClientInitialization:
    """Tests for EdgeTTSClient initialization."""

    def test_initializes_with_default_voice(self):
        """Test that client initializes with default voice."""
        client = EdgeTTSClient()
        assert client._voice_id == "vi-VN-HoaiMyNeural"

    def test_initializes_with_custom_voice(self):
        """Test that client initializes with custom voice."""
        client = EdgeTTSClient(voice_id="vi-VN-NamMinhNeural")
        assert client._voice_id == "vi-VN-NamMinhNeural"


class TestGenerateAudio:
    """Tests for generate_audio method."""

    @pytest.mark.asyncio
    async def test_generate_audio_creates_file(self, tts_client):
        """Test that generate_audio creates an audio file."""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            # Mock edge_tts.Communicate
            mock_communicate = AsyncMock()
            mock_communicate.save = AsyncMock()

            with patch("src.ttsgen.tts_client.edge_tts.Communicate") as mock_comm_class, \
                 patch.object(tts_client, "_get_audio_duration", return_value=2.5):

                mock_comm_class.return_value = mock_communicate

                # Generate audio
                duration = await tts_client.generate_audio(
                    "Xin chào, đây là bài kiểm tra", temp_path
                )

                # Verify Communicate was called with correct parameters
                mock_comm_class.assert_called_once_with(
                    "Xin chào, đây là bài kiểm tra",
                    "vi-VN-HoaiMyNeural",
                )

                # Verify save was called
                mock_communicate.save.assert_called_once_with(temp_path)

                # Verify duration was returned
                assert duration == 2.5

        finally:
            # Clean up
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_generate_audio_handles_empty_text(self, tts_client):
        """Test that empty text is handled gracefully."""
        duration = await tts_client.generate_audio("", "/tmp/test.mp3")
        assert duration == 0.0

    @pytest.mark.asyncio
    async def test_generate_audio_handles_whitespace_only(self, tts_client):
        """Test that whitespace-only text is handled gracefully."""
        duration = await tts_client.generate_audio("   \n  \t  ", "/tmp/test.mp3")
        assert duration == 0.0

    @pytest.mark.asyncio
    async def test_generate_audio_completes_successfully(self, tts_client):
        """Test that audio generation completes successfully."""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            mock_communicate = AsyncMock()
            mock_communicate.save = AsyncMock()

            with patch("src.ttsgen.tts_client.edge_tts.Communicate") as mock_comm_class, \
                 patch.object(tts_client, "_get_audio_duration", return_value=1.5):

                mock_comm_class.return_value = mock_communicate

                duration = await tts_client.generate_audio("Test text", temp_path)

                # Verify the generation completed and returned duration
                assert duration == 1.5
                mock_communicate.save.assert_called_once()

        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_generate_audio_with_vietnamese_text(self, tts_client):
        """Test audio generation with Vietnamese text."""
        vietnamese_text = "Đây là một câu chuyện về One Piece"

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            mock_communicate = AsyncMock()
            mock_communicate.save = AsyncMock()

            with patch("src.ttsgen.tts_client.edge_tts.Communicate") as mock_comm_class, \
                 patch.object(tts_client, "_get_audio_duration", return_value=3.0):

                mock_comm_class.return_value = mock_communicate

                duration = await tts_client.generate_audio(vietnamese_text, temp_path)

                # Verify Vietnamese text was passed correctly
                mock_comm_class.assert_called_once_with(
                    vietnamese_text,
                    "vi-VN-HoaiMyNeural",
                )

                assert duration == 3.0

        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestGenerateAudioBytes:
    """Tests for generate_audio_bytes method."""

    @pytest.mark.asyncio
    async def test_generate_audio_bytes_returns_bytes_and_duration(self, tts_client):
        """Test that generate_audio_bytes returns bytes and duration."""
        test_audio_data = b"fake mp3 data"

        with patch.object(tts_client, "generate_audio", return_value=2.0) as mock_gen, \
             patch("builtins.open", create=True) as mock_open, \
             patch("os.unlink"):

            # Mock file read
            mock_file = MagicMock()
            mock_file.read.return_value = test_audio_data
            mock_file.__enter__.return_value = mock_file
            mock_open.return_value = mock_file

            audio_bytes, duration = await tts_client.generate_audio_bytes(
                "Test text"
            )

            # Verify generate_audio was called
            assert mock_gen.call_count == 1

            # Verify results
            assert audio_bytes == test_audio_data
            assert duration == 2.0

    @pytest.mark.asyncio
    async def test_generate_audio_bytes_handles_empty_text(self, tts_client):
        """Test that empty text returns empty bytes."""
        audio_bytes, duration = await tts_client.generate_audio_bytes("")

        assert audio_bytes == b""
        assert duration == 0.0

    @pytest.mark.asyncio
    async def test_generate_audio_bytes_cleans_up_temp_file(self, tts_client):
        """Test that temporary file is cleaned up."""
        with patch.object(tts_client, "generate_audio", return_value=1.5), \
             patch("builtins.open", create=True) as mock_open, \
             patch("os.unlink") as mock_unlink:

            mock_file = MagicMock()
            mock_file.read.return_value = b"test data"
            mock_file.__enter__.return_value = mock_file
            mock_open.return_value = mock_file

            await tts_client.generate_audio_bytes("Test")

            # Verify temp file was deleted
            assert mock_unlink.call_count == 1

    @pytest.mark.asyncio
    async def test_generate_audio_bytes_cleans_up_on_error(self, tts_client):
        """Test that temp file is cleaned up even on error."""
        with patch.object(tts_client, "generate_audio", side_effect=Exception("Test error")), \
             patch("os.unlink") as mock_unlink:

            with pytest.raises(Exception, match="Test error"):
                await tts_client.generate_audio_bytes("Test")

            # Verify temp file was still deleted
            assert mock_unlink.call_count == 1


class TestGetAudioDuration:
    """Tests for _get_audio_duration method."""

    def test_get_audio_duration_reads_mp3_duration(self, tts_client):
        """Test that MP3 duration is read correctly."""
        with patch("src.ttsgen.tts_client.MP3") as mock_mp3:
            mock_audio = MagicMock()
            mock_audio.info.length = 5.25
            mock_mp3.return_value = mock_audio

            duration = tts_client._get_audio_duration("/path/to/audio.mp3")

            assert duration == 5.25
            mock_mp3.assert_called_once_with("/path/to/audio.mp3")

    def test_get_audio_duration_handles_error(self, tts_client):
        """Test that errors in reading duration are handled."""
        with patch("src.ttsgen.tts_client.MP3", side_effect=Exception("Read error")):
            duration = tts_client._get_audio_duration("/path/to/audio.mp3")

            # Should return 0.0 on error
            assert duration == 0.0


class TestGetAvailableVietnameseVoices:
    """Tests for get_available_vietnamese_voices method."""

    @pytest.mark.asyncio
    async def test_filters_vietnamese_voices_only(self, sample_vietnamese_voices):
        """Test that only Vietnamese voices are returned."""
        with patch("src.ttsgen.tts_client.edge_tts.list_voices", return_value=sample_vietnamese_voices):
            voices = await EdgeTTSClient.get_available_vietnamese_voices()

            # Should only return vi-VN voices (2 out of 3)
            assert len(voices) == 2

            # Verify voice IDs
            voice_ids = [v["voice_id"] for v in voices]
            assert "vi-VN-HoaiMyNeural" in voice_ids
            assert "vi-VN-NamMinhNeural" in voice_ids
            assert "en-US-JennyNeural" not in voice_ids

    @pytest.mark.asyncio
    async def test_returns_correct_voice_structure(self, sample_vietnamese_voices):
        """Test that voice dictionaries have correct structure."""
        with patch("src.ttsgen.tts_client.edge_tts.list_voices", return_value=sample_vietnamese_voices):
            voices = await EdgeTTSClient.get_available_vietnamese_voices()

            # Verify structure of first voice
            assert "voice_id" in voices[0]
            assert "name" in voices[0]
            assert "gender" in voices[0]

            # Verify values
            assert voices[0]["voice_id"] == "vi-VN-HoaiMyNeural"
            assert "HoaiMy" in voices[0]["name"]
            assert voices[0]["gender"] == "Female"

    @pytest.mark.asyncio
    async def test_handles_error_gracefully(self):
        """Test that errors are handled gracefully."""
        with patch("src.ttsgen.tts_client.edge_tts.list_voices", side_effect=Exception("API error")):
            voices = await EdgeTTSClient.get_available_vietnamese_voices()

            # Should return empty list on error
            assert voices == []

    @pytest.mark.asyncio
    async def test_handles_empty_voice_list(self):
        """Test handling of empty voice list."""
        with patch("src.ttsgen.tts_client.edge_tts.list_voices", return_value=[]):
            voices = await EdgeTTSClient.get_available_vietnamese_voices()

            assert voices == []


class TestSyncWrappers:
    """Tests for synchronous wrapper functions."""

    def test_generate_audio_sync_wrapper(self):
        """Test synchronous wrapper for generate_audio."""
        with patch("src.ttsgen.tts_client.EdgeTTSClient.generate_audio", return_value=2.5) as mock_gen, \
             patch("src.ttsgen.tts_client.asyncio.run") as mock_run:

            # Make asyncio.run just call the coroutine's result
            mock_run.return_value = 2.5

            duration = generate_audio_sync(
                "Test text",
                "/tmp/output.mp3",
                "vi-VN-HoaiMyNeural",
            )

            # Verify asyncio.run was called
            assert mock_run.call_count == 1
            assert duration == 2.5

    def test_generate_audio_bytes_sync_wrapper(self):
        """Test synchronous wrapper for generate_audio_bytes."""
        with patch("src.ttsgen.tts_client.EdgeTTSClient.generate_audio_bytes") as mock_gen, \
             patch("src.ttsgen.tts_client.asyncio.run") as mock_run:

            mock_run.return_value = (b"audio data", 1.5)

            audio_bytes, duration = generate_audio_bytes_sync(
                "Test text",
                "vi-VN-HoaiMyNeural",
            )

            assert mock_run.call_count == 1
            assert audio_bytes == b"audio data"
            assert duration == 1.5

    def test_get_vietnamese_voices_sync_wrapper(self):
        """Test synchronous wrapper for get_available_vietnamese_voices."""
        expected_voices = [
            {"voice_id": "vi-VN-HoaiMyNeural", "name": "HoaiMy", "gender": "Female"}
        ]

        with patch("src.ttsgen.tts_client.EdgeTTSClient.get_available_vietnamese_voices") as mock_get, \
             patch("src.ttsgen.tts_client.asyncio.run") as mock_run:

            mock_run.return_value = expected_voices

            voices = get_vietnamese_voices_sync()

            assert mock_run.call_count == 1
            assert voices == expected_voices


# Integration test (requires network, marked as slow)
@pytest.mark.slow
@pytest.mark.asyncio
async def test_generate_audio_integration():
    """Integration test that actually calls Edge TTS API."""
    client = EdgeTTSClient(voice_id="vi-VN-HoaiMyNeural")

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
        temp_path = temp_file.name

    try:
        # Generate audio with Vietnamese text
        vietnamese_text = "Xin chào. Đây là một bài kiểm tra."
        duration = await client.generate_audio(vietnamese_text, temp_path)

        # Verify file was created
        assert os.path.exists(temp_path)

        # Verify file has content
        file_size = os.path.getsize(temp_path)
        assert file_size > 0

        # Verify duration is reasonable (should be a few seconds)
        assert duration > 0.5
        assert duration < 10.0

    finally:
        # Clean up
        if os.path.exists(temp_path):
            os.unlink(temp_path)


@pytest.mark.slow
@pytest.mark.asyncio
async def test_get_vietnamese_voices_integration():
    """Integration test for fetching Vietnamese voices."""
    voices = await EdgeTTSClient.get_available_vietnamese_voices()

    # Should have at least 1 Vietnamese voice
    assert len(voices) > 0

    # Verify structure
    for voice in voices:
        assert "voice_id" in voice
        assert "name" in voice
        assert "gender" in voice
        assert voice["voice_id"].startswith("vi-VN")
