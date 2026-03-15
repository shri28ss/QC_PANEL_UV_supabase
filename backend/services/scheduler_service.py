"""
Scheduler Service.
Uses APScheduler to trigger random QC checks on a configurable schedule.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from services.random_qc_service import run_random_qc
import logging

logger = logging.getLogger(__name__)

# Create a single scheduler instance
scheduler = BackgroundScheduler()


def start_scheduler():
    """Called when the FastAPI server starts."""
    
    # Add the random QC job
    scheduler.add_job(
        run_random_qc,           # The sfunction to call
        'cron',                  # Trigger type: cron = time-based schedule
        hour=2,                 # At 2 AM
        minute=00,               # At :00 minutes
        id='random_qc_job',      # Unique ID so we can reference it later
        replace_existing=True,   # If server restarts, don't create duplicate
        kwargs={'sample_size': 1}  # How many random docs to check
    )
    
    scheduler.start()
    logger.info("Scheduler started. Random QC will run daily at 2:00 AM.")


def stop_scheduler():
    """Called when the FastAPI server stops."""
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped.")
