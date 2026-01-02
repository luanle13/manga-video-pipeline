from __future__ import annotations
from celery import Celery
from celery.schedules import crontab
from ..celery_app import app
from . import tasks
from ..pipeline.workflow import start_daily_batch_pipeline


# Configure the beat schedule for periodic tasks
app.conf.beat_schedule = {
    # Discover trending manga every 2 hours
    'discover-trending': {
        'task': 'src.pipeline.tasks.discover_trending_manga',
        'schedule': crontab(minute=0, hour='*/2'),  # Every 2 hours at minute 0
    },

    # Process batch of manga every 2 hours, 30 minutes after discovery
    'process-batch': {
        'task': 'src.scheduler.jobs.process_daily_batch_task',
        'schedule': crontab(minute=30, hour='*/2'),  # Every 2 hours at minute 30
    },

    # Retry failed tasks every 4 hours
    'retry-failed': {
        'task': 'src.scheduler.jobs.retry_failed_uploads',
        'schedule': crontab(minute=0, hour='*/4'),  # Every 4 hours
    },

    # Send daily summary at 11 PM
    'daily-summary': {
        'task': 'src.scheduler.jobs.send_daily_summary',
        'schedule': crontab(minute=0, hour=23),  # 11 PM UTC
    },

    # Clean up old temporary files at 4 AM
    'cleanup-old-temp': {
        'task': 'src.scheduler.jobs.cleanup_old_temp_files',
        'schedule': crontab(minute=0, hour=4),  # 4 AM UTC
    },
}

# Also update the app configuration with the schedule
app.conf.timezone = 'UTC'


# Define the custom periodic tasks that are referenced above
@app.task
def process_daily_batch_task():
    """Task to process a daily batch of manga chapters."""
    from ..pipeline.workflow import start_daily_batch_pipeline

    # In a real implementation, fetch trending manga from database or cache
    # For now, use placeholder data
    manga_list = [
        {
            'title': 'Example Manga',
            'url': 'https://example.com/manga',
            'chapters': [1.0, 1.1],
            'language': 'en',
            'voice': 'alloy'
        }
    ]

    # Start the batch processing
    results = start_daily_batch_pipeline(manga_list)

    return {
        'batch_size': len(manga_list),
        'tasks_started': len(results),
        'task_ids': [result.task_id for result in results]
    }


@app.task
def retry_failed_uploads():
    """Task to retry failed uploads."""
    from ..db import get_db_session, PipelineRun

    session = get_db_session()

    # Find failed pipeline runs
    failed_runs = session.query(PipelineRun).filter(
        PipelineRun.status == 'error'
    ).all()

    retry_count = 0
    for run in failed_runs:
        # Implement retry logic here
        # For now, just log the retry
        print(f"Retrying failed task: {run.task_id}")
        retry_count += 1

    session.close()

    return {
        'failed_tasks_found': len(failed_runs),
        'retry_attempts': retry_count
    }


@app.task
def send_daily_summary():
    """Task to send daily summary statistics."""
    from ..db import get_db_session, PipelineRun
    from datetime import datetime, timedelta

    session = get_db_session()

    # Calculate stats for the last 24 hours
    yesterday = datetime.utcnow() - timedelta(days=1)

    total_runs = session.query(PipelineRun).count()
    completed_runs = session.query(PipelineRun).filter(
        PipelineRun.status == 'completed'
    ).count()
    failed_runs = session.query(PipelineRun).filter(
        PipelineRun.status == 'error'
    ).count()

    # Additional stats
    stats = {
        'date': datetime.utcnow().isoformat(),
        'total_runs': total_runs,
        'completed_runs': completed_runs,
        'failed_runs': failed_runs,
        'success_rate': (completed_runs / total_runs * 100) if total_runs > 0 else 0,
        'errors_count': failed_runs
    }

    # Send notification with daily summary
    from ..notifications.telegram import TelegramNotifier
    import os

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if bot_token and chat_id:
        notifier = TelegramNotifier(bot_token, chat_id)
        # Send the daily summary using the notifier
        import asyncio
        from asgiref.sync import async_to_sync

        async def _send_summary():
            await notifier.send_daily_summary(stats)

        async_to_sync(_send_summary)()

    session.close()

    return stats


@app.task
def cleanup_old_temp_files():
    """Task to clean up old temporary files."""
    import os
    import tempfile
    from datetime import datetime, timedelta
    
    temp_dir = tempfile.gettempdir()
    current_time = datetime.utcnow()
    cleaned_count = 0
    
    for filename in os.listdir(temp_dir):
        if 'manga_video_pipeline' in filename:  # Our temp files have this pattern
            file_path = os.path.join(temp_dir, filename)
            
            # Check if the file is older than 24 hours
            file_time = datetime.fromtimestamp(os.path.getctime(file_path))
            if current_time - file_time > timedelta(hours=24):
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        cleaned_count += 1
                        print(f"Cleaned up old temp file: {file_path}")
                except Exception as e:
                    print(f"Failed to clean up {file_path}: {e}")
    
    return {
        'files_cleaned': cleaned_count,
        'directory': temp_dir
    }