"""
Profitability router — per-SKU and per-order profit views.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import logging

from ..database import supabase

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/profitability", tags=["Profitability"])


# ── Per-SKU profitability ──────────────────────────────────────────────────

@router.get("/sku")
async def get_sku_profitability(
    sort_by: str = Query("total_net_profit", description="Column to sort by"),
    sort_desc: bool = True,
    limit: int = Query(100, ge=1, le=500),
):
    """
    Get per-SKU profitability from the v_sku_profitability view.
    Formula: Revenue - Amazon Fees - Shipping Cost - COGS = Net Profit
    Uses historical unit_cogs snapshots for accuracy.
    """
    try:
        response = (
            supabase.table("v_sku_profitability")
            .select("*")
            .order(sort_by, desc=sort_desc)
            .limit(limit)
            .execute()
        )
        return {
            "sku_profitability": response.data,
            "count": len(response.data),
        }
    except Exception as e:
        logger.error(f"SKU profitability error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Per-order profitability ────────────────────────────────────────────────

@router.get("/orders")
async def get_order_profitability(
    days: int = Query(30, ge=1, le=365),
    channel: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    Get per-order profitability from the v_order_profitability view.
    Includes breakdown: revenue, fees, shipping, COGS, net profit, margin %.
    """
    try:
        from datetime import datetime, timedelta, timezone
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        query = (
            supabase.table("v_order_profitability")
            .select("*")
            .gte("purchase_date", since)
        )

        if channel:
            query = query.eq("fulfillment_channel", channel)

        response = (
            query.order("purchase_date", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

        return {
            "order_profitability": response.data,
            "count": len(response.data),
        }
    except Exception as e:
        logger.error(f"Order profitability error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Financial events raw view ──────────────────────────────────────────────

@router.get("/financial-events/{amazon_order_id}")
async def get_financial_events(amazon_order_id: str):
    """Get raw financial events for an order — useful for debugging fee breakdowns."""
    try:
        response = (
            supabase.table("financial_events")
            .select("*")
            .eq("amazon_order_id", amazon_order_id)
            .order("posted_date", desc=True)
            .execute()
        )
        return {"events": response.data, "count": len(response.data)}
    except Exception as e:
        logger.error(f"Financial events error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
