"""
Sync router — cron-ready endpoints to trigger SP-API data syncs.

These endpoints are designed to be called by:
- Internal scheduler (APScheduler)
- External cron (Render cron jobs, Railway cron, etc.)
- Manual trigger from the dashboard
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import Optional
import logging

from ..services.order_sync import sync_orders
from ..services.inventory_sync import sync_inventory
from ..services.finance_sync import sync_financial_events, sync_financial_events_for_order

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sync", tags=["Data Sync"])


# ── Order sync ─────────────────────────────────────────────────────────────

@router.post("/orders")
async def trigger_order_sync(
    background_tasks: BackgroundTasks,
    days_back: int = Query(7, ge=1, le=90),
    async_mode: bool = Query(True, description="Run in background"),
):
    """
    Trigger SP-API order sync.
    Fetches orders, line items, snapshots COGS, and calculates profitability.
    """
    if async_mode:
        background_tasks.add_task(sync_orders, days_back=days_back)
        return {
            "status": "started",
            "message": f"Order sync started (last {days_back} days)",
            "mode": "background",
        }
    else:
        try:
            result = sync_orders(days_back=days_back)
            return {"status": "completed", **result}
        except Exception as e:
            logger.error(f"Order sync failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))


# ── Inventory sync ─────────────────────────────────────────────────────────

@router.post("/inventory")
async def trigger_inventory_sync(
    background_tasks: BackgroundTasks,
    async_mode: bool = Query(True),
):
    """
    Trigger SP-API FBA inventory sync.
    Fetches all FBA inventory summaries and upserts into warehouse_inventory.
    """
    if async_mode:
        background_tasks.add_task(sync_inventory)
        return {
            "status": "started",
            "message": "Inventory sync started",
            "mode": "background",
        }
    else:
        try:
            result = sync_inventory()
            return {"status": "completed", **result}
        except Exception as e:
            logger.error(f"Inventory sync failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))


# ── Finance sync ───────────────────────────────────────────────────────────

@router.post("/finances")
async def trigger_finance_sync(
    background_tasks: BackgroundTasks,
    days_back: int = Query(7, ge=1, le=90),
    async_mode: bool = Query(True),
):
    """
    Trigger SP-API financial events sync.
    Fetches fee data and reconciles into order_items for accurate profitability.
    """
    if async_mode:
        background_tasks.add_task(sync_financial_events, days_back=days_back)
        return {
            "status": "started",
            "message": f"Finance sync started (last {days_back} days)",
            "mode": "background",
        }
    else:
        try:
            result = sync_financial_events(days_back=days_back)
            return {"status": "completed", **result}
        except Exception as e:
            logger.error(f"Finance sync failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))


# ── Full sync (all three) ─────────────────────────────────────────────────

@router.post("/all")
async def trigger_full_sync(
    background_tasks: BackgroundTasks,
    days_back: int = Query(7, ge=1, le=90),
):
    """
    Trigger all three syncs in sequence: Orders → Inventory → Finances.
    Always runs in background due to the time required.
    """
    async def _run_full_sync(days: int):
        logger.info(f"Starting full sync (last {days} days)")
        try:
            order_result = sync_orders(days_back=days)
            logger.info(f"Order sync done: {order_result}")
        except Exception as e:
            logger.error(f"Order sync failed in full sync: {e}")

        try:
            inv_result = sync_inventory()
            logger.info(f"Inventory sync done: {inv_result}")
        except Exception as e:
            logger.error(f"Inventory sync failed in full sync: {e}")

        try:
            fin_result = sync_financial_events(days_back=days)
            logger.info(f"Finance sync done: {fin_result}")
        except Exception as e:
            logger.error(f"Finance sync failed in full sync: {e}")

        logger.info("Full sync complete")

    background_tasks.add_task(_run_full_sync, days_back)

    return {
        "status": "started",
        "message": f"Full sync started (Orders → Inventory → Finances, last {days_back} days)",
        "mode": "background",
    }


# ── Dimensions sync ────────────────────────────────────────────────────────

from ..services.dimensions_sync import sync_dimensions_batch

@router.post("/dimensions")
async def trigger_dimensions_sync(
    background_tasks: BackgroundTasks,
    limit: int = Query(50, ge=1, le=500),
    async_mode: bool = Query(True),
):
    """
    Sync missing product dimensions from SP-API Catalog.
    Processes in real-time batches.
    """
    if async_mode:
        background_tasks.add_task(sync_dimensions_batch, limit)
        return {
            "status": "started",
            "message": f"Dimensions sync started for up to {limit} SKUs",
            "mode": "background",
        }
    else:
        try:
            result = sync_dimensions_batch(limit=limit)
            return {"status": "completed", **result}
        except Exception as e:
            logger.error(f"Dimensions sync failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

