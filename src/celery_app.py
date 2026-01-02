from __future__ import annotations
import os
from celery import Celery
from kombu import Queue


# Create Celery application instance
app = Celery('manga_video_pipeline')

# Configuration
app.config_from_object({
    # Broker configuration (Redis)
    'broker_url': os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    'result_backend': os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    
    # Task serializer
    'task_serializer': 'json',
    'accept_content': ['json'],
    'result_serializer': 'json',
    
    # Timezone settings
    'timezone': os.getenv('TZ', 'UTC'),
    'enable_utc': True,
    
    # Result expiration (24 hours)
    'result_expires': 86400,
    
    # Task routing
    'task_routes': {
        'pipeline.tasks.*': {'queue': 'pipeline_tasks'},
        'daily_batch.*': {'queue': 'daily_batch'},
    },
    
    # Custom queues
    'task_default_queue': 'default',
    'task_queues': (
        Queue('default', routing_key='default'),
        Queue('pipeline_tasks', routing_key='pipeline_tasks'),
        Queue('daily_batch', routing_key='daily_batch'),
        Queue('high_priority', routing_key='high_priority'),
    ),
    
    # Task retry settings
    'task_retry_policy': {
        'max_retries': 3,
        'interval_start': 0,
        'interval_step': 1,
        'interval_max': 10,
    },
    
    # Worker settings
    'worker_prefetch_multiplier': 1,
    'task_acks_late': True,
    
    # Beat scheduler settings
    'beat_schedule': {
        # This will be configured in the jobs module
    },
    
    # Python 3.13 compatibility settings
    'broker_connection_retry_on_startup': True,
    'broker_pool_limit': 10,
    'result_backend_transport_options': {
        'visibility_timeout': 18000,  # 5 hours
    },
})

# Auto-discover tasks from the pipeline.tasks module
app.autodiscover_tasks(['src.pipeline.tasks'])

if __name__ == '__main__':
    app.start()