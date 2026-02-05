"""RQ Worker with logging and graceful shutdown."""

import os
import signal
import sys
import logging
import uuid
from redis import Redis
from rq import Worker, Queue
from config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


class GracefulWorker(Worker):
    """Worker with graceful shutdown handling."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._shutdown_requested = False
    
    def request_stop(self, signum, frame):
        """Handle shutdown signal gracefully."""
        logger.info("Shutdown requested. Finishing current job...")
        self._shutdown_requested = True
        super().request_stop(signum, frame)


def run_worker():
    """Start the RQ worker with priority queue support."""
    logger.info("=" * 50)
    logger.info("AI Ops Assistant - Worker Starting")
    logger.info("=" * 50)
    
    # Connect to Redis
    try:
        redis_conn = Redis.from_url(settings.redis_url)
        redis_conn.ping()
        logger.info(f"Connected to Redis: {settings.redis_url}")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        sys.exit(1)
    
    # Setup queues (priority order: high > default > low)
    queues = [
        Queue("high", connection=redis_conn),
        Queue("default", connection=redis_conn),
        Queue("low", connection=redis_conn),
    ]
    logger.info(f"Listening on queues: high, default, low")
    
    # Create worker
    # Use a unique worker name to avoid collisions when multiple workers connect
    worker_name = f"worker-{uuid.uuid4().hex[:8]}"
    worker = GracefulWorker(
        queues,
        connection=redis_conn,
        name=worker_name,
    )
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, worker.request_stop)
    signal.signal(signal.SIGINT, worker.request_stop)
    
    logger.info("Worker ready. Waiting for tasks...")
    logger.info("-" * 50)
    
    # Start processing
    try:
        worker.work(with_scheduler=False)
    except Exception as e:
        logger.error(f"Worker error: {e}")
        sys.exit(1)
    finally:
        logger.info("Worker stopped.")


if __name__ == "__main__":
    run_worker()
