"""Unit tests for spot interruption handler."""

import json
import signal
from unittest.mock import MagicMock, patch

import pytest

from src.renderer.spot_handler import (
    delete_checkpoint,
    load_checkpoint,
    register_spot_interruption_handler,
    save_checkpoint,
)


@pytest.fixture
def mock_s3_client():
    """Mock S3 client."""
    return MagicMock()


class TestCheckpointSaveLoad:
    """Tests for checkpoint save and load operations."""

    def test_saves_checkpoint_to_s3(self, mock_s3_client):
        """Test that checkpoint data is saved to S3."""
        job_id = "test-job-123"
        checkpoint_data = {"last_completed_chunk": 5, "total_chunks": 10}

        save_checkpoint(job_id, checkpoint_data, mock_s3_client)

        # Verify S3 put_object was called
        mock_s3_client.put_object.assert_called_once()

        # Verify checkpoint key
        call_args = mock_s3_client.put_object.call_args
        checkpoint_key = call_args[0][0]
        assert checkpoint_key == f"jobs/{job_id}/checkpoint.json"

        # Verify checkpoint content
        checkpoint_bytes = call_args[0][1]
        saved_data = json.loads(checkpoint_bytes.decode("utf-8"))
        assert saved_data == checkpoint_data

    def test_loads_checkpoint_from_s3(self, mock_s3_client):
        """Test that checkpoint data is loaded from S3."""
        job_id = "test-job-123"
        checkpoint_data = {"last_completed_chunk": 3}

        # Mock S3 download
        checkpoint_json = json.dumps(checkpoint_data)
        mock_s3_client.download_as_bytes.return_value = checkpoint_json.encode("utf-8")

        result = load_checkpoint(job_id, mock_s3_client)

        # Verify download was called with correct key
        mock_s3_client.download_as_bytes.assert_called_once_with(
            f"jobs/{job_id}/checkpoint.json"
        )

        # Verify loaded data
        assert result == checkpoint_data

    def test_returns_none_when_checkpoint_not_found(self, mock_s3_client):
        """Test that None is returned when checkpoint doesn't exist."""
        job_id = "test-job-123"

        # Mock S3 download returning None (file not found)
        mock_s3_client.download_as_bytes.return_value = None

        result = load_checkpoint(job_id, mock_s3_client)

        assert result is None

    def test_returns_none_on_load_error(self, mock_s3_client):
        """Test that None is returned when loading fails."""
        job_id = "test-job-123"

        # Mock S3 download raising exception
        mock_s3_client.download_as_bytes.side_effect = Exception("S3 error")

        result = load_checkpoint(job_id, mock_s3_client)

        assert result is None

    def test_checkpoint_round_trip(self, mock_s3_client):
        """Test save and load round-trip."""
        job_id = "test-job-123"
        checkpoint_data = {
            "last_completed_chunk": 7,
            "total_chunks": 20,
            "timestamp": "2024-01-01T00:00:00",
        }

        # Save checkpoint
        save_checkpoint(job_id, checkpoint_data, mock_s3_client)

        # Get saved data from mock call
        call_args = mock_s3_client.put_object.call_args
        saved_bytes = call_args[0][1]

        # Mock load to return saved data
        mock_s3_client.download_as_bytes.return_value = saved_bytes

        # Load checkpoint
        loaded_data = load_checkpoint(job_id, mock_s3_client)

        # Verify round-trip
        assert loaded_data == checkpoint_data


class TestCheckpointDeletion:
    """Tests for checkpoint deletion."""

    def test_deletes_checkpoint_from_s3(self, mock_s3_client):
        """Test that checkpoint is deleted from S3."""
        job_id = "test-job-123"

        delete_checkpoint(job_id, mock_s3_client)

        # Verify delete_object was called
        mock_s3_client.delete_object.assert_called_once_with(
            f"jobs/{job_id}/checkpoint.json"
        )

    def test_deletion_handles_errors_gracefully(self, mock_s3_client):
        """Test that deletion errors are handled gracefully."""
        job_id = "test-job-123"

        # Mock delete raising exception
        mock_s3_client.delete_object.side_effect = Exception("S3 error")

        # Should not raise exception
        delete_checkpoint(job_id, mock_s3_client)


class TestSpotInterruptionHandler:
    """Tests for spot interruption handler registration."""

    def test_registers_sigterm_handler(self, mock_s3_client):
        """Test that SIGTERM handler is registered."""
        job_id = "test-job-123"

        with patch("signal.signal") as mock_signal:
            register_spot_interruption_handler(job_id, mock_s3_client)

            # Verify signal handler was registered
            mock_signal.assert_called_once()
            call_args = mock_signal.call_args
            assert call_args[0][0] == signal.SIGTERM
            assert callable(call_args[0][1])

    def test_registers_handler_with_callback(self, mock_s3_client):
        """Test handler registration with checkpoint callback."""
        job_id = "test-job-123"

        checkpoint_callback = MagicMock(return_value={"chunk": 5})

        with patch("signal.signal") as mock_signal:
            register_spot_interruption_handler(
                job_id, mock_s3_client, checkpoint_callback
            )

            # Verify handler was registered
            mock_signal.assert_called_once()

    def test_sigterm_handler_saves_checkpoint(self, mock_s3_client):
        """Test that SIGTERM handler saves checkpoint."""
        job_id = "test-job-123"
        checkpoint_data = {"last_completed_chunk": 3}

        checkpoint_callback = MagicMock(return_value=checkpoint_data)

        with patch("signal.signal") as mock_signal, \
             patch("sys.exit") as mock_exit:

            register_spot_interruption_handler(
                job_id, mock_s3_client, checkpoint_callback
            )

            # Get the registered handler
            handler = mock_signal.call_args[0][1]

            # Simulate SIGTERM
            handler(signal.SIGTERM, None)

            # Verify checkpoint callback was called
            checkpoint_callback.assert_called_once()

            # Verify checkpoint was saved
            mock_s3_client.put_object.assert_called_once()

            # Verify sys.exit was called
            mock_exit.assert_called_once_with(0)

    def test_sigterm_handler_without_callback(self, mock_s3_client):
        """Test SIGTERM handler without checkpoint callback."""
        job_id = "test-job-123"

        with patch("signal.signal") as mock_signal, \
             patch("sys.exit") as mock_exit:

            register_spot_interruption_handler(job_id, mock_s3_client, None)

            # Get the registered handler
            handler = mock_signal.call_args[0][1]

            # Simulate SIGTERM
            handler(signal.SIGTERM, None)

            # Verify checkpoint was saved (empty)
            mock_s3_client.put_object.assert_called_once()

            # Verify sys.exit was called
            mock_exit.assert_called_once_with(0)

    def test_sigterm_handler_handles_save_errors(self, mock_s3_client):
        """Test that SIGTERM handler handles checkpoint save errors."""
        job_id = "test-job-123"

        # Mock S3 put_object to raise exception
        mock_s3_client.put_object.side_effect = Exception("S3 error")

        with patch("signal.signal") as mock_signal, \
             patch("sys.exit") as mock_exit:

            register_spot_interruption_handler(job_id, mock_s3_client, None)

            # Get the registered handler
            handler = mock_signal.call_args[0][1]

            # Simulate SIGTERM - should not raise exception
            handler(signal.SIGTERM, None)

            # Verify sys.exit was still called (graceful exit despite error)
            mock_exit.assert_called_once_with(0)


class TestCheckpointDataStructure:
    """Tests for checkpoint data structure validation."""

    def test_handles_complex_checkpoint_data(self, mock_s3_client):
        """Test saving and loading complex checkpoint data."""
        job_id = "test-job-123"
        checkpoint_data = {
            "last_completed_chunk": 15,
            "total_chunks": 50,
            "timestamp": "2024-01-01T12:00:00Z",
            "metadata": {
                "scene_count": 1500,
                "duration": 7200.5,
            },
        }

        save_checkpoint(job_id, checkpoint_data, mock_s3_client)

        # Get saved data
        call_args = mock_s3_client.put_object.call_args
        saved_bytes = call_args[0][1]
        loaded_data = json.loads(saved_bytes.decode("utf-8"))

        # Verify structure is preserved
        assert loaded_data == checkpoint_data
        assert loaded_data["metadata"]["scene_count"] == 1500

    def test_handles_empty_checkpoint_data(self, mock_s3_client):
        """Test saving and loading empty checkpoint."""
        job_id = "test-job-123"
        checkpoint_data = {}

        save_checkpoint(job_id, checkpoint_data, mock_s3_client)

        # Get saved data
        call_args = mock_s3_client.put_object.call_args
        saved_bytes = call_args[0][1]
        loaded_data = json.loads(saved_bytes.decode("utf-8"))

        assert loaded_data == {}


class TestCheckpointS3Keys:
    """Tests for checkpoint S3 key formatting."""

    def test_uses_correct_s3_key_format(self, mock_s3_client):
        """Test that checkpoint uses correct S3 key format."""
        job_id = "my-job-456"

        save_checkpoint(job_id, {}, mock_s3_client)

        # Verify S3 key format
        call_args = mock_s3_client.put_object.call_args
        checkpoint_key = call_args[0][0]
        assert checkpoint_key == "jobs/my-job-456/checkpoint.json"

    def test_load_uses_correct_s3_key(self, mock_s3_client):
        """Test that load uses correct S3 key."""
        job_id = "another-job-789"

        mock_s3_client.download_as_bytes.return_value = None

        load_checkpoint(job_id, mock_s3_client)

        # Verify S3 key format
        mock_s3_client.download_as_bytes.assert_called_once_with(
            "jobs/another-job-789/checkpoint.json"
        )

    def test_delete_uses_correct_s3_key(self, mock_s3_client):
        """Test that delete uses correct S3 key."""
        job_id = "delete-job-111"

        delete_checkpoint(job_id, mock_s3_client)

        # Verify S3 key format
        mock_s3_client.delete_object.assert_called_once_with(
            "jobs/delete-job-111/checkpoint.json"
        )
