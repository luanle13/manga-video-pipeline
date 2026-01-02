import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
import tempfile
from dataclasses import dataclass


@dataclass
class MockPipelineRun:
    """Mock class for PipelineRun."""
    manga_title: str
    chapter_number: float
    language: str
    status: str = "pending"
    id: int = 1
    task_id: str = "test_task_id"


class TestPipelineWorkflow:
    """Test cases for the Pipeline Workflow."""
    
    @pytest.mark.asyncio
    async def test_process_chapter_happy_path(self):
        """Test the full pipeline for a single chapter."""
        from src.pipeline.workflow import PipelineWorkflow
        workflow = PipelineWorkflow()
        
        with patch('src.pipeline.tasks.scrape_chapter') as mock_scrape, \
             patch('src.pipeline.tasks.generate_summary') as mock_summary, \
             patch('src.pipeline.tasks.generate_audio') as mock_audio, \
             patch('src.pipeline.tasks.generate_video') as mock_video, \
             patch('src.pipeline.tasks.generate_metadata') as mock_metadata, \
             patch('src.pipeline.tasks.upload_to_platform') as mock_upload, \
             patch('src.pipeline.tasks.send_notification') as mock_notify, \
             patch('src.pipeline.tasks.cleanup_temp_files') as mock_cleanup:
            
            # Mock task returns
            mock_scrape.si.return_value = AsyncMock()
            mock_summary.si.return_value = AsyncMock()
            mock_audio.si.return_value = AsyncMock()
            mock_video.si.return_value = AsyncMock()
            mock_metadata.si.return_value = AsyncMock()
            mock_upload.si.return_value = AsyncMock()
            mock_notify.si.return_value = AsyncMock()
            mock_cleanup.si.return_value = AsyncMock()
            
            # Mock the celery chain
            with patch('celery.chain') as mock_chain:
                mock_result = AsyncMock()
                mock_chain.return_value.apply_async.return_value = mock_result
                mock_result.task_id = "test_task_chain_id"
                
                # Run the pipeline
                result = await workflow.process_chapter(
                    manga_title="One Piece",
                    manga_url="https://example.com/onepiece",
                    chapter_number=1001.0,
                    language="en",
                    voice="alloy"
                )
                
                # Verify the chain was created properly
                assert mock_chain.called
                assert result.task_id == "test_task_chain_id"
                
                # Verify the run was added to the session
                # This would need to be verified differently depending on the db implementation
    
    @pytest.mark.asyncio
    async def test_process_chapter_with_error_handling(self):
        """Test the full pipeline with error handling."""
        from src.pipeline.workflow import PipelineWorkflow
        workflow = PipelineWorkflow()
        
        with patch('src.pipeline.tasks.scrape_chapter') as mock_scrape, \
             patch('src.pipeline.tasks.generate_summary') as mock_summary, \
             patch('src.pipeline.tasks.generate_audio') as mock_audio, \
             patch('src.pipeline.tasks.generate_video') as mock_video, \
             patch('src.pipeline.tasks.generate_metadata') as mock_metadata, \
             patch('src.pipeline.tasks.upload_to_platform') as mock_upload, \
             patch('src.pipeline.tasks.send_notification') as mock_notify, \
             patch('src.pipeline.tasks.cleanup_temp_files') as mock_cleanup, \
             patch('celery.chain') as mock_chain:
            
            # Mock task returns
            mock_scrape.si.return_value = AsyncMock()
            mock_summary.si.return_value = AsyncMock()
            mock_audio.si.return_value = AsyncMock()
            mock_video.si.return_value = AsyncMock()
            mock_metadata.si.return_value = AsyncMock()
            mock_upload.si.return_value = AsyncMock()
            mock_notify.si.return_value = AsyncMock()
            mock_cleanup.si.return_value = AsyncMock()
            
            # Simulate a failure in one of the tasks
            mock_chain.side_effect = Exception("Pipeline failure")
            
            # Should handle the error gracefully
            with pytest.raises(Exception, match="Pipeline failure"):
                await workflow.process_chapter(
                    manga_title="One Piece",
                    manga_url="https://example.com/onepiece",
                    chapter_number=1001.0,
                    language="en",
                    voice="alloy"
                )
    
    @pytest.mark.asyncio
    async def test_process_daily_batch_happy_path(self):
        """Test the daily batch processing pipeline."""
        from src.pipeline.workflow import PipelineWorkflow
        workflow = PipelineWorkflow()
        
        manga_list = [
            {
                'title': 'One Piece',
                'url': 'https://example.com/onepiece',
                'chapters': [1001.0, 1002.0],
                'language': 'en',
                'voice': 'alloy'
            },
            {
                'title': 'Naruto',
                'url': 'https://example.com/naruto',
                'chapters': [700.0],
                'language': 'vn',
                'voice': 'echo'
            }
        ]
        
        with patch.object(workflow, 'process_chapter') as mock_process_chapter:
            mock_result = AsyncMock()
            mock_result.task_id = "test_task_id"
            mock_process_chapter.return_value = mock_result
            
            # Run the batch processing
            results = await workflow.process_daily_batch(manga_list)
            
            # We should have 3 chapters processed (2 from One Piece, 1 from Naruto)
            assert len(results) == 3
            
            # Verify the method was called with the correct parameters
            assert mock_process_chapter.call_count == 3
            calls = mock_process_chapter.call_args_list
            
            # Verify the first call
            assert calls[0][0][0] == 'One Piece'  # manga_title
            assert calls[0][0][1] == 'https://example.com/onepiece'  # manga_url
            assert calls[0][0][2] == 1001.0  # chapter_number
            assert calls[0][0][3] == 'en'  # language
            assert calls[0][0][4] == 'alloy'  # voice
            
            # Verify the second call
            assert calls[1][0][0] == 'One Piece'  # manga_title
            assert calls[1][0][2] == 1002.0  # chapter_number
            
            # Verify the third call
            assert calls[2][0][0] == 'Naruto'  # manga_title
            assert calls[2][0][1] == 'https://example.com/naruto'  # manga_url
            assert calls[2][0][2] == 700.0  # chapter_number
            assert calls[2][0][3] == 'vn'  # language
            assert calls[2][0][4] == 'echo'  # voice
    
    @pytest.mark.asyncio
    async def test_process_daily_batch_with_empty_list(self):
        """Test batch processing with an empty list."""
        from src.pipeline.workflow import PipelineWorkflow
        workflow = PipelineWorkflow()
        
        manga_list = []
        
        with patch.object(workflow, 'process_chapter') as mock_process_chapter:
            mock_result = AsyncMock()
            mock_result.task_id = "test_task_id"
            mock_process_chapter.return_value = mock_result
            
            # Run the batch processing with empty list
            results = await workflow.process_daily_batch(manga_list)
            
            # Should have no results
            assert len(results) == 0
            assert mock_process_chapter.call_count == 0
    
    @pytest.mark.asyncio
    async def test_process_daily_batch_with_mixed_success_and_failure(self):
        """Test batch processing when some chapters succeed and some fail."""
        from src.pipeline.workflow import PipelineWorkflow
        workflow = PipelineWorkflow()
        
        manga_list = [
            {
                'title': 'One Piece',
                'url': 'https://example.com/onepiece',
                'chapters': [1001.0],
                'language': 'en',
                'voice': 'alloy'
            },
            {
                'title': 'Naruto', 
                'url': 'https://example.com/naruto',
                'chapters': [700.0],
                'language': 'en',
                'voice': 'alloy'
            }
        ]
        
        with patch.object(workflow, 'process_chapter') as mock_process_chapter:
            # First call succeeds, second fails
            mock_result1 = AsyncMock()
            mock_result1.task_id = "test_task_id_1"
            
            mock_process_chapter.side_effect = [
                mock_result1,
                Exception("Second chapter failed")
            ]
            
            # The first chapter should be processed successfully
            # The second should raise an exception, which would be caught by the caller
            with pytest.raises(Exception, match="Second chapter failed"):
                await workflow.process_daily_batch(manga_list)
    
    @pytest.mark.asyncio
    async def test_process_chapter_with_special_characters(self):
        """Test processing chapters with special characters in titles."""
        from src.pipeline.workflow import PipelineWorkflow
        workflow = PipelineWorkflow()
        
        with patch('src.pipeline.tasks.scrape_chapter') as mock_scrape, \
             patch('src.pipeline.tasks.generate_summary') as mock_summary, \
             patch('src.pipeline.tasks.generate_audio') as mock_audio, \
             patch('src.pipeline.tasks.generate_video') as mock_video, \
             patch('src.pipeline.tasks.generate_metadata') as mock_metadata, \
             patch('src.pipeline.tasks.upload_to_platform') as mock_upload, \
             patch('src.pipeline.tasks.send_notification') as mock_notify, \
             patch('src.pipeline.tasks.cleanup_temp_files') as mock_cleanup, \
             patch('celery.chain') as mock_chain:
            
            # Mock task returns
            mock_scrape.si.return_value = AsyncMock()
            mock_summary.si.return_value = AsyncMock()
            mock_audio.si.return_value = AsyncMock()
            mock_video.si.return_value = AsyncMock()
            mock_metadata.si.return_value = AsyncMock()
            mock_upload.si.return_value = AsyncMock()
            mock_notify.si.return_value = AsyncMock()
            mock_cleanup.si.return_value = AsyncMock()
            
            mock_result = AsyncMock()
            mock_chain.return_value.apply_async.return_value = mock_result
            mock_result.task_id = "test_task_id_special"
            
            # Test with special characters in title
            result = await workflow.process_chapter(
                manga_title="One Piece: Special Edition!",
                manga_url="https://example.com/onepiece-special",
                chapter_number=1001.5,
                language="en",
                voice="fable"
            )
            
            assert result.task_id == "test_task_id_special"
    
    @pytest.mark.asyncio
    async def test_process_chapter_with_vietnamese_language(self):
        """Test processing a chapter with Vietnamese language."""
        from src.pipeline.workflow import PipelineWorkflow
        workflow = PipelineWorkflow()
        
        with patch('src.pipeline.tasks.scrape_chapter') as mock_scrape, \
             patch('src.pipeline.tasks.generate_summary') as mock_summary, \
             patch('src.pipeline.tasks.generate_audio') as mock_audio, \
             patch('src.pipeline.tasks.generate_video') as mock_video, \
             patch('src.pipeline.tasks.generate_metadata') as mock_metadata, \
             patch('src.pipeline.tasks.upload_to_platform') as mock_upload, \
             patch('src.pipeline.tasks.send_notification') as mock_notify, \
             patch('src.pipeline.tasks.cleanup_temp_files') as mock_cleanup, \
             patch('celery.chain') as mock_chain:
            
            # Mock task returns
            mock_scrape.si.return_value = AsyncMock()
            mock_summary.si.return_value = AsyncMock()
            mock_audio.si.return_value = AsyncMock()
            mock_video.si.return_value = AsyncMock()
            mock_metadata.si.return_value = AsyncMock()
            mock_upload.si.return_value = AsyncMock()
            mock_notify.si.return_value = AsyncMock()
            mock_cleanup.si.return_value = AsyncMock()
            
            mock_result = AsyncMock()
            mock_chain.return_value.apply_async.return_value = mock_result
            mock_result.task_id = "test_task_id_vn"
            
            # Test with Vietnamese language
            result = await workflow.process_chapter(
                manga_title="Đại Chiến Titan",
                manga_url="https://example.com/attackontitan-vn",
                chapter_number=139.0,
                language="vn",  # Vietnamese
                voice="nova"
            )
            
            assert result.task_id == "test_task_id_vn"
    
    @pytest.mark.asyncio
    async def test_process_chapter_edge_cases(self):
        """Test processing chapter with edge cases."""
        from src.pipeline.workflow import PipelineWorkflow
        workflow = PipelineWorkflow()
        
        with patch('src.pipeline.tasks.scrape_chapter') as mock_scrape, \
             patch('src.pipeline.tasks.generate_summary') as mock_summary, \
             patch('src.pipeline.tasks.generate_audio') as mock_audio, \
             patch('src.pipeline.tasks.generate_video') as mock_video, \
             patch('src.pipeline.tasks.generate_metadata') as mock_metadata, \
             patch('src.pipeline.tasks.upload_to_platform') as mock_upload, \
             patch('src.pipeline.tasks.send_notification') as mock_notify, \
             patch('src.pipeline.tasks.cleanup_temp_files') as mock_cleanup, \
             patch('celery.chain') as mock_chain:
            
            # Mock task returns
            mock_scrape.si.return_value = AsyncMock()
            mock_summary.si.return_value = AsyncMock()
            mock_audio.si.return_value = AsyncMock()
            mock_video.si.return_value = AsyncMock()
            mock_metadata.si.return_value = AsyncMock()
            mock_upload.si.return_value = AsyncMock()
            mock_notify.si.return_value = AsyncMock()
            mock_cleanup.si.return_value = AsyncMock()
            
            mock_result = AsyncMock()
            mock_chain.return_value.apply_async.return_value = mock_result
            mock_result.task_id = "test_task_id_edge"
            
            # Test with floating point chapter number edge cases
            result = await workflow.process_chapter(
                manga_title="Test Manga",
                manga_url="https://example.com/test",
                chapter_number=0.5,  # Fractional chapter
                language="en",
                voice="alloy"
            )
            
            assert result.task_id == "test_task_id_edge"
            
            # Test with large chapter number
            result2 = await workflow.process_chapter(
                manga_title="Long Running Series",
                manga_url="https://example.com/longrunning",
                chapter_number=9999.0,  # Large chapter number
                language="en",
                voice="alloy"
            )
            
            # Verify different tasks were called
            assert mock_scrape.si.call_count == 2
    
    @pytest.mark.asyncio
    async def test_standalone_start_functions(self):
        """Test the standalone start_*_pipeline functions."""
        from src.pipeline.workflow import start_single_chapter_pipeline, start_daily_batch_pipeline
        
        manga_info = {
            'title': 'Test Manga',
            'url': 'https://example.com/test',
            'chapters': [1.0],
            'language': 'en',
            'voice': 'alloy'
        }
        
        manga_list = [manga_info]
        
        with patch('src.pipeline.workflow.PipelineWorkflow') as mock_workflow_class:
            mock_workflow = AsyncMock()
            mock_result = AsyncMock()
            mock_result.task_id = "test_standalone_task_id"
            
            mock_workflow.process_chapter.return_value = mock_result
            mock_workflow.process_daily_batch.return_value = [mock_result]
            
            mock_workflow_class.return_value = mock_workflow
            
            # Test standalone single chapter function
            single_result = await start_single_chapter_pipeline(
                manga_title="Test Manga",
                manga_url="https://example.com/test",
                chapter_number=1.0,
                language="en",
                voice="alloy"
            )
            
            assert single_result.task_id == "test_standalone_task_id"
            
            # Test standalone batch function
            batch_results = await start_daily_batch_pipeline(manga_list)
            
            assert len(batch_results) == 1
            assert batch_results[0].task_id == "test_standalone_task_id"