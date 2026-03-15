"""
Dashboard router — KPI summary, orders list, SKU management.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime, timedelta, timezone
import logging

from ..database import supabase
from ..models import SellerBoardDashboardSummary, COGSUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Dashboard"])


# ── Dashboard KPI Summary ──────────────────────────────────────────────────

def _aggregate_tile(data: list) -> dict:
    gross = sum(float(r.get("line_item_revenue") or 0) for r in data)
    net = sum(float(r.get("net_profit") or 0) for r in data)
    # Since we are modifying Veeqo UI, we map existing data or default ad_spend/shipping for the view
    ad_sq = sum(float(r.get("ad_spend") or 0) for r in data) 
    ship_cost = sum(float(r.get("total_shipping_cost") or 0) for r in data)
    units = len(data) # Simple count matching items
    margin = (net / gross * 100) if gross > 0 else 0
    return {
        "gross_sales": round(gross, 2),
        "units_sold": units,
        "ad_spend": round(ad_sq, 2),
        "estimated_shipping": round(ship_cost, 2),
        "net_profit": round(net, 2),
        "margin_pct": round(margin, 2)
    }

@router.get("/dashboard/summary", response_model=SellerBoardDashboardSummary)
async def get_dashboard_summary(
    days: int = Query(30, ge=1, le=365, description="Number of days to aggregate"),
):
    """
    Get backend logic matching phase 3 SellerBoard Tiles.
    """
    try:
        now = datetime.now(timezone.utc)
        since = (now - timedelta(days=60)).isoformat() # get 60 days to cover last month

        profit_resp = (
            supabase.table("v_order_profitability")
            .select("*")
            .gte("purchase_date", since)
            .execute()
        )
        
        data = profit_resp.data

        # Filter sets 
        today_data = [r for r in data if r.get("purchase_date", "").startswith(now.strftime("%Y-%m-%d"))]
        yesterday = now - timedelta(days=1)
        yesterday_data = [r for r in data if r.get("purchase_date", "").startswith(yesterday.strftime("%Y-%m-%d"))]
        
        # MTD
        start_mtd = now.replace(day=1)
        mtd_data =  [r for r in data if r.get("purchase_date") >= start_mtd.isoformat()]
        
        # Last Month
        first_day_this_month = now.replace(day=1)
        last_day_last_month = first_day_this_month - timedelta(days=1)
        first_day_last_month = last_day_last_month.replace(day=1)
        last_month_data = [r for r in data if first_day_last_month.isoformat() <= r.get("purchase_date") <= first_day_this_month.isoformat()]

        # Compute Tiles
        today_tile = _aggregate_tile(today_data)
        yesterday_tile = _aggregate_tile(yesterday_data)
        mtd_tile = _aggregate_tile(mtd_data)
        last_month_tile = _aggregate_tile(last_month_data)

        # Legacy logic fallback
        total_revenue = 0.0
        total_net_profit = 0.0
        fba_orders = 0
        fbm_orders = 0

        for row in profit_resp.data:
            total_revenue += float(row.get("line_item_revenue", 0))
            total_net_profit += float(row.get("net_profit", 0))
            if row.get("fulfillment_channel") == "FBA":
                fba_orders += 1
            else:
                fbm_orders += 1

        total_orders = fba_orders + fbm_orders
        avg_margin = (total_net_profit / total_revenue * 100) if total_revenue > 0 else 0

        # SKU count
        sku_resp = (
            supabase.table("sku_master")
            .select("sku", count="exact")
            .eq("is_active", True)
            .execute()
        )
        total_skus = sku_resp.count or 0

        # Inventory units
        inv_resp = (
            supabase.table("warehouse_inventory")
            .select("quantity")
            .execute()
        )
        total_inventory = sum(r.get("quantity", 0) for r in inv_resp.data)

        return SellerBoardDashboardSummary(
            today=today_tile,
            yesterday=yesterday_tile,
            mtd=mtd_tile,
            last_month=last_month_tile,
            total_revenue=round(total_revenue, 2),
            total_orders=total_orders,
            total_net_profit=round(total_net_profit, 2),
            avg_margin_pct=round(avg_margin, 2),
            fba_orders=fba_orders,
            fbm_orders=fbm_orders,
            total_skus=total_skus,
            total_inventory_units=total_inventory,
        )
    except Exception as e:
        logger.error(f"Dashboard summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Orders list ────────────────────────────────────────────────────────────

@router.get("/orders")
async def get_orders(
    status: Optional[str] = None,
    channel: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Get orders with optional filters."""
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        query = (
            supabase.table("orders")
            .select("*")
            .gte("purchase_date", since)
        )

        if status:
            query = query.eq("order_status", status)
        if channel:
            query = query.eq("fulfillment_channel", channel)

        response = (
            query.order("purchase_date", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

        return {"orders": response.data, "count": len(response.data)}
    except Exception as e:
        logger.error(f"Orders fetch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Order items ────────────────────────────────────────────────────────────

@router.get("/orders/{order_id}/items")
async def get_order_items(order_id: str):
    """Get line items for a specific order."""
    try:
        response = (
            supabase.table("order_items")
            .select("*")
            .eq("order_id", order_id)
            .execute()
        )
        return {"items": response.data}
    except Exception as e:
        logger.error(f"Order items fetch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── SKU Master ─────────────────────────────────────────────────────────────

@router.get("/skus")
async def get_skus(
    channel: Optional[str] = None,
    active_only: bool = True,
):
    """Get all SKUs with optional filters."""
    try:
        query = supabase.table("sku_master").select("*")

        if channel:
            query = query.eq("channel", channel)
        if active_only:
            query = query.eq("is_active", True)

        response = query.order("sku").execute()
        return {"skus": response.data, "count": len(response.data)}
    except Exception as e:
        logger.error(f"SKUs fetch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/skus/{sku}/cogs")
async def update_cogs(sku: str, update: COGSUpdate):
    """
    Update COGS for a SKU. Only affects FUTURE orders.
    Historical profitability is preserved via order_items.unit_cogs snapshot.
    """
    try:
        response = (
            supabase.table("sku_master")
            .update({"cogs": update.cogs})
            .eq("sku", sku)
            .execute()
        )

        if not response.data:
            raise HTTPException(status_code=404, detail=f"SKU {sku} not found")

        return {
            "message": f"COGS updated for {sku}",
            "sku": sku,
            "new_cogs": update.cogs,
            "note": "Only future orders will use this COGS value.",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"COGS update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
