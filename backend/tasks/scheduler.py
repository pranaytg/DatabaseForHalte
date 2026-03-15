"""
Background scheduler — runs SP-API syncs on a cron schedule.

Uses APScheduler to run syncs at intervals that respect free-tier rate limits.
Designed to be lightweight and avoid overlapping runs.
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

from ..services.order_sync import sync_orders
from ..services.inventory_sync import sync_inventory
from ..services.finance_sync import sync_financial_events

logger = logging.getLogger(__name__)

def job_listener(event):
    if event.exception:
        logger.error(f"Job {event.job_id} failed with exception: {event.exception}")
    else:
        logger.info(f"Job {event.job_id} completed successfully.")

scheduler = BackgroundScheduler(
    job_defaults={
        "coalesce": True,       # Skip missed runs, don't stack
        "max_instances": 1,     # Prevent overlapping runs
        "misfire_grace_time": 300,
    }
)
scheduler.add_listener(job_listener, EVENT_JOB_ERROR | EVENT_JOB_EXECUTED)


def init_scheduler():
    """
    Initialize and start the background scheduler.
    
    Schedule (optimized for free-tier limits):
    - Orders:    every 4 hours (moderate API usage)
    - Inventory: every 6 hours (low API usage)
    - Finances:  every 12 hours (heavy API usage)
    """
    # Order sync — every 4 hours, look back 1 day
    scheduler.add_job(
        sync_orders,
        trigger=IntervalTrigger(hours=4),
        kwargs={"days_back": 1},
        id="sync_orders",
        name="SP-API Order Sync",
        replace_existing=True,
    )

    # Inventory sync — every 6 hours
    scheduler.add_job(
        sync_inventory,
        trigger=IntervalTrigger(hours=6),
        id="sync_inventory",
        name="SP-API Inventory Sync",
        replace_existing=True,
    )

    # Finance sync — every 12 hours, look back 2 days
    scheduler.add_job(
        sync_financial_events,
        trigger=IntervalTrigger(hours=12),
        kwargs={"days_back": 2},
        id="sync_finances",
        name="SP-API Finance Sync",
        replace_existing=True,
    )

    # Dimensions sync — every 24 hours
    from ..services.dimensions_sync import sync_dimensions_batch
    scheduler.add_job(
        sync_dimensions_batch,
        trigger=IntervalTrigger(hours=24),
        kwargs={"limit": 50},
        id="sync_dimensions",
        name="SP-API Dimensions Sync",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started with 4 sync jobs")


def shutdown_scheduler():
    """Gracefully shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down")
