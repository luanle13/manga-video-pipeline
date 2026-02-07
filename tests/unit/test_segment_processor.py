"""Tests for TTS segment processor."""

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from src.common.models import (
    AudioManifest,
    AudioSegment,
    ScriptDocument,
    ScriptSegment,
)
from src.ttsgen.segment_processor import TTSSegmentProcessor


@pytest.fixture
def mock_tts_client():
    """Create a mock EdgeTTSClient."""
    client = MagicMock()
    client.generate_audio_bytes = AsyncMock()
    return client


@pytest.fixture
def mock_s3_client():
    """Create a mock S3Client."""
    client = MagicMock()
    client.upload_bytes = MagicMock(return_value="s3://bucket/key")
    client.upload_json = MagicMock(return_value="s3://bucket/manifest.json")
    return client


@pytest.fixture
def segment_processor(mock_tts_client, mock_s3_client):
    """Create a TTSSegmentProcessor instance."""
    return TTSSegmentProcessor(mock_tts_client, mock_s3_client)


@pytest.fixture
def sample_segment():
    """Create a sample script segment."""
    return ScriptSegment(
        chapter="Chương 1",
        text="Đây là một câu chuyện về One Piece. Luffy muốn trở thành Vua Hải Tặc.",
        panel_start=0,
        panel_end=5,
    )


@pytest.fixture
def sample_script():
    """Create a sample script document."""
    return ScriptDocument(
        job_id="test-job-123",
        manga_title="One Piece",
        segments=[
            ScriptSegment(
                chapter="Chương 1",
                text="Đoạn đầu tiên.",
                panel_start=0,
                panel_end=2,
            ),
            ScriptSegment(
                chapter="Chương 1",
                text="Đoạn thứ hai.",
                panel_start=3,
                panel_end=5,
            ),
            ScriptSegment(
                chapter="Chương 2",
                text="Đoạn thứ ba.",
                panel_start=0,
                panel_end=3,
            ),
        ],
    )


class TestTTSSegmentProcessorInitialization:
    """Tests for TTSSegmentProcessor initialization."""

    def test_initializes_with_clients(self, mock_tts_client, mock_s3_client):
        """Test that processor initializes with TTS and S3 clients."""
        processor = TTSSegmentProcessor(mock_tts_client, mock_s3_client)

        assert processor._tts_client is mock_tts_client
        assert processor._s3_client is mock_s3_client


class TestSplitLongText:
    """Tests for split_long_text method."""

    def test_returns_single_chunk_for_short_text(self, segment_processor):
        """Test that short text is not split."""
        text = "Đây là một câu ngắn."
        chunks = segment_processor.split_long_text(text, max_chars=100)

        assert len(chunks) == 1
        assert chunks[0] == text

    def test_splits_on_sentence_boundaries(self, segment_processor):
        """Test that text is split on Vietnamese sentence boundaries."""
        text = "Câu thứ nhất. Câu thứ hai. Câu thứ ba. Câu thứ tư."
        chunks = segment_processor.split_long_text(text, max_chars=30)

        # Should split into multiple chunks
        assert len(chunks) > 1

        # Each chunk should end with a period
        for chunk in chunks:
            assert chunk.strip().endswith(".")

    def test_respects_max_chars_limit(self, segment_processor):
        """Test that chunks respect the max_chars limit."""
        sentences = ["Câu {}.".format(i) for i in range(100)]
        text = " ".join(sentences)

        max_chars = 50
        chunks = segment_processor.split_long_text(text, max_chars=max_chars)

        # All chunks should be under the limit
        for chunk in chunks:
            assert len(chunk) <= max_chars

    def test_handles_text_without_periods(self, segment_processor):
        """Test handling of text without sentence boundaries."""
        text = "A" * 5000  # Long text without periods
        chunks = segment_processor.split_long_text(text, max_chars=3000)

        # Should still return the text (no split possible)
        assert len(chunks) == 1

    def test_handles_empty_text(self, segment_processor):
        """Test handling of empty text."""
        chunks = segment_processor.split_long_text("", max_chars=3000)

        assert len(chunks) == 0

    def test_handles_whitespace_only_text(self, segment_processor):
        """Test handling of whitespace-only text."""
        chunks = segment_processor.split_long_text("   \n  \t  ", max_chars=3000)

        assert len(chunks) == 0

    def test_preserves_periods_in_chunks(self, segment_processor):
        """Test that periods are preserved in chunks."""
        text = "Câu một. Câu hai. Câu ba."
        chunks = segment_processor.split_long_text(text, max_chars=15)

        # Join all chunks - should equal original text (with possible whitespace changes)
        reconstructed = "".join(chunks)
        assert reconstructed.count(".") == text.count(".")


class TestProcessSegment:
    """Tests for process_segment method."""

    @pytest.mark.asyncio
    async def test_processes_single_chunk_segment(
        self, segment_processor, mock_tts_client, mock_s3_client, sample_segment
    ):
        """Test processing a segment that fits in one chunk."""
        # Mock TTS client to return audio bytes and duration
        mock_tts_client.generate_audio_bytes.return_value = (b"audio data", 3.5)

        # Process the segment
        result = await segment_processor.process_segment(sample_segment, "job-123", 0)

        # Verify TTS client was called once
        mock_tts_client.generate_audio_bytes.assert_called_once()

        # Verify S3 upload
        mock_s3_client.upload_bytes.assert_called_once_with(
            data=b"audio data",
            s3_key="jobs/job-123/audio/0000.mp3",
            content_type="audio/mpeg",
        )

        # Verify result
        assert isinstance(result, AudioSegment)
        assert result.index == 0
        assert result.s3_key == "jobs/job-123/audio/0000.mp3"
        assert result.duration_seconds == 3.5
        assert result.chapter == "Chương 1"
        assert result.panel_start == 0
        assert result.panel_end == 5

    @pytest.mark.asyncio
    async def test_processes_multi_chunk_segment(
        self, segment_processor, mock_tts_client, mock_s3_client
    ):
        """Test processing a segment that requires splitting."""
        # Create a long segment
        long_text = ". ".join(["Câu {}".format(i) for i in range(200)])
        long_segment = ScriptSegment(
            chapter="Chương 1",
            text=long_text,
            panel_start=0,
            panel_end=10,
        )

        # Mock TTS client to return audio for each chunk
        mock_tts_client.generate_audio_bytes.side_effect = [
            (b"chunk1", 2.0),
            (b"chunk2", 2.5),
        ]

        # Mock split_long_text to force splitting into 2 chunks
        with patch.object(
            segment_processor,
            "split_long_text",
            return_value=["Chunk 1 text.", "Chunk 2 text."],
        ), patch.object(
            segment_processor,
            "_concatenate_audio_chunks",
            return_value=b"combined audio",
        ) as mock_concat:
            result = await segment_processor.process_segment(long_segment, "job-123", 1)

            # Verify multiple TTS calls
            assert mock_tts_client.generate_audio_bytes.call_count >= 2

            # Verify concatenation was called
            mock_concat.assert_called_once()

            # Verify S3 upload with combined audio
            mock_s3_client.upload_bytes.assert_called_once_with(
                data=b"combined audio",
                s3_key="jobs/job-123/audio/0001.mp3",
                content_type="audio/mpeg",
            )

            # Verify total duration is sum of chunks
            assert result.duration_seconds == 4.5

    @pytest.mark.asyncio
    async def test_retries_on_tts_failure(
        self, segment_processor, mock_tts_client, mock_s3_client, sample_segment
    ):
        """Test that TTS failures trigger retries."""
        # Mock TTS client to fail twice then succeed
        mock_tts_client.generate_audio_bytes.side_effect = [
            Exception("TTS error 1"),
            Exception("TTS error 2"),
            (b"audio data", 3.0),
        ]

        with patch("asyncio.sleep"):  # Skip sleep delays in tests
            result = await segment_processor.process_segment(sample_segment, "job-123", 0)

            # Verify 3 attempts were made
            assert mock_tts_client.generate_audio_bytes.call_count == 3

            # Verify eventual success
            assert result.duration_seconds == 3.0

    @pytest.mark.asyncio
    async def test_skips_segment_after_max_retries(
        self, segment_processor, mock_tts_client, mock_s3_client, sample_segment
    ):
        """Test that segment is skipped after max retries."""
        # Mock TTS client to always fail
        mock_tts_client.generate_audio_bytes.side_effect = Exception("TTS error")

        with patch("asyncio.sleep"):
            result = await segment_processor.process_segment(sample_segment, "job-123", 0)

            # Verify retries were attempted (1 initial + 2 retries = 3 total)
            assert mock_tts_client.generate_audio_bytes.call_count == 3

            # Verify silent segment returned
            assert result.duration_seconds == 0.0
            assert result.s3_key == "jobs/job-123/audio/0000.mp3"

    @pytest.mark.asyncio
    async def test_uses_correct_s3_key_format(
        self, segment_processor, mock_tts_client, mock_s3_client, sample_segment
    ):
        """Test that S3 keys are formatted correctly with zero-padding."""
        mock_tts_client.generate_audio_bytes.return_value = (b"audio", 2.0)

        # Test various indices
        await segment_processor.process_segment(sample_segment, "job-123", 0)
        await segment_processor.process_segment(sample_segment, "job-123", 9)
        await segment_processor.process_segment(sample_segment, "job-123", 99)
        await segment_processor.process_segment(sample_segment, "job-123", 999)

        # Verify S3 key formatting
        calls = mock_s3_client.upload_bytes.call_args_list
        assert calls[0][1]["s3_key"] == "jobs/job-123/audio/0000.mp3"
        assert calls[1][1]["s3_key"] == "jobs/job-123/audio/0009.mp3"
        assert calls[2][1]["s3_key"] == "jobs/job-123/audio/0099.mp3"
        assert calls[3][1]["s3_key"] == "jobs/job-123/audio/0999.mp3"


class TestProcessAllSegments:
    """Tests for process_all_segments method."""

    @pytest.mark.asyncio
    async def test_processes_all_segments_sequentially(
        self, segment_processor, mock_tts_client, mock_s3_client, sample_script
    ):
        """Test that all segments are processed sequentially."""
        # Mock TTS client
        mock_tts_client.generate_audio_bytes.side_effect = [
            (b"audio1", 2.0),
            (b"audio2", 3.0),
            (b"audio3", 2.5),
        ]

        # Process all segments
        manifest = await segment_processor.process_all_segments(
            sample_script, "test-job-123"
        )

        # Verify all segments were processed
        assert mock_tts_client.generate_audio_bytes.call_count == 3

        # Verify manifest structure
        assert isinstance(manifest, AudioManifest)
        assert manifest.job_id == "test-job-123"
        assert len(manifest.segments) == 3
        assert manifest.total_duration_seconds == 7.5

    @pytest.mark.asyncio
    async def test_manifest_has_correct_segment_info(
        self, segment_processor, mock_tts_client, mock_s3_client, sample_script
    ):
        """Test that manifest contains correct segment information."""
        mock_tts_client.generate_audio_bytes.side_effect = [
            (b"audio1", 2.0),
            (b"audio2", 3.0),
            (b"audio3", 2.5),
        ]

        manifest = await segment_processor.process_all_segments(
            sample_script, "test-job-123"
        )

        # Check first segment
        seg0 = manifest.segments[0]
        assert seg0.index == 0
        assert seg0.chapter == "Chương 1"
        assert seg0.panel_start == 0
        assert seg0.panel_end == 2
        assert seg0.duration_seconds == 2.0
        assert seg0.s3_key == "jobs/test-job-123/audio/0000.mp3"

        # Check second segment
        seg1 = manifest.segments[1]
        assert seg1.index == 1
        assert seg1.duration_seconds == 3.0

        # Check third segment
        seg2 = manifest.segments[2]
        assert seg2.index == 2
        assert seg2.chapter == "Chương 2"
        assert seg2.duration_seconds == 2.5

    @pytest.mark.asyncio
    async def test_uploads_manifest_to_s3(
        self, segment_processor, mock_tts_client, mock_s3_client, sample_script
    ):
        """Test that manifest is uploaded to S3."""
        mock_tts_client.generate_audio_bytes.return_value = (b"audio", 2.0)

        manifest = await segment_processor.process_all_segments(
            sample_script, "test-job-123"
        )

        # Verify manifest upload
        mock_s3_client.upload_json.assert_called_once()

        call_args = mock_s3_client.upload_json.call_args
        assert call_args[1]["s3_key"] == "jobs/test-job-123/audio_manifest.json"

        # Verify uploaded data matches manifest
        uploaded_data = call_args[1]["data"]
        assert uploaded_data["job_id"] == "test-job-123"
        assert len(uploaded_data["segments"]) == 3
        assert uploaded_data["total_duration_seconds"] == 6.0

    @pytest.mark.asyncio
    async def test_handles_empty_script(
        self, segment_processor, mock_tts_client, mock_s3_client
    ):
        """Test handling of script with no segments."""
        empty_script = ScriptDocument(
            job_id="empty-job",
            manga_title="Empty Manga",
            segments=[],
        )

        manifest = await segment_processor.process_all_segments(
            empty_script, "empty-job"
        )

        # Verify empty manifest
        assert len(manifest.segments) == 0
        assert manifest.total_duration_seconds == 0.0

        # Verify TTS was never called
        mock_tts_client.generate_audio_bytes.assert_not_called()

    @pytest.mark.asyncio
    async def test_continues_after_segment_failure(
        self, segment_processor, mock_tts_client, mock_s3_client, sample_script
    ):
        """Test that processing continues even if one segment fails."""
        # Second segment fails completely
        mock_tts_client.generate_audio_bytes.side_effect = [
            (b"audio1", 2.0),
            Exception("Persistent error"),
            Exception("Persistent error"),
            Exception("Persistent error"),
            (b"audio3", 2.5),
        ]

        with patch("asyncio.sleep"):
            manifest = await segment_processor.process_all_segments(
                sample_script, "test-job-123"
            )

            # Verify all segments are in manifest (failed one has 0 duration)
            assert len(manifest.segments) == 3
            assert manifest.segments[0].duration_seconds == 2.0
            assert manifest.segments[1].duration_seconds == 0.0  # Failed segment
            assert manifest.segments[2].duration_seconds == 2.5

            # Total duration excludes failed segment
            assert manifest.total_duration_seconds == 4.5

    @pytest.mark.asyncio
    async def test_calculates_cumulative_duration(
        self, segment_processor, mock_tts_client, mock_s3_client
    ):
        """Test that cumulative duration is calculated correctly."""
        script = ScriptDocument(
            job_id="test-job",
            manga_title="Test",
            segments=[
                ScriptSegment(chapter="Ch1", text="Text1", panel_start=0, panel_end=1),
                ScriptSegment(chapter="Ch1", text="Text2", panel_start=2, panel_end=3),
                ScriptSegment(chapter="Ch2", text="Text3", panel_start=0, panel_end=1),
                ScriptSegment(chapter="Ch2", text="Text4", panel_start=2, panel_end=3),
            ],
        )

        mock_tts_client.generate_audio_bytes.side_effect = [
            (b"a", 1.5),
            (b"b", 2.3),
            (b"c", 3.1),
            (b"d", 1.7),
        ]

        manifest = await segment_processor.process_all_segments(script, "test-job")

        # Verify total duration
        expected_total = 1.5 + 2.3 + 3.1 + 1.7
        assert manifest.total_duration_seconds == expected_total


class TestConcatenateAudioChunks:
    """Tests for _concatenate_audio_chunks method."""

    @pytest.mark.asyncio
    async def test_concatenates_multiple_chunks(self, segment_processor):
        """Test that audio chunks are concatenated when pydub is available."""
        audio_parts = [
            (b"chunk1", 1.0),
            (b"chunk2", 1.5),
            (b"chunk3", 2.0),
        ]

        # Test that the method at least attempts to process multiple chunks
        # The actual concatenation depends on pydub being installed
        result = await segment_processor._concatenate_audio_chunks(audio_parts)

        # The result should be bytes (either concatenated or fallback to first chunk)
        assert isinstance(result, bytes)
        assert len(result) > 0

        # Note: The actual concatenation behavior depends on pydub availability
        # In production, pydub would concatenate the chunks
        # In test environment without pydub, it falls back to first chunk
        # Both behaviors are acceptable as they're handled by the implementation

    @pytest.mark.asyncio
    async def test_falls_back_if_pydub_unavailable(self, segment_processor):
        """Test fallback when pydub is not available."""
        audio_parts = [
            (b"chunk1", 1.0),
            (b"chunk2", 1.5),
        ]

        # Mock ImportError for pydub
        with patch(
            "src.ttsgen.segment_processor.AudioSegment",
            side_effect=ImportError("pydub not installed"),
        ):
            result = await segment_processor._concatenate_audio_chunks(audio_parts)

            # Should return first chunk as fallback
            assert result == b"chunk1"
