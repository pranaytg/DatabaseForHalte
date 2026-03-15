"""
Inventory router — warehouse inventory views and FBM stock management.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime, timedelta, timezone
import logging

from ..database import supabase

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/inventory", tags=["Inventory"])


# ── Warehouse summary ──────────────────────────────────────────────────────

@router.get("/summary")
async def get_warehouse_summary():
    """
    Get aggregated inventory per warehouse from the v_warehouse_summary view.
    Shows FBA vs FBM split, SKU counts, and stock levels.
    """
    try:
        response = supabase.table("v_warehouse_summary").select("*").execute()
        return {"warehouses": response.data}
    except Exception as e:
        logger.error(f"Warehouse summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Detailed inventory ─────────────────────────────────────────────────────

@router.get("/")
async def get_inventory(
    channel: Optional[str] = Query(None, description="FBA or FBM"),
    warehouse_id: Optional[str] = None,
    sku: Optional[str] = None,
    low_stock: bool = Query(False, description="Only show items at or below reorder point"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Get detailed inventory with optional filters."""
    try:
        query = (
            supabase.table("warehouse_inventory")
            .select("*, sku_master(product_name, asin, cogs, is_active)")
        )

        if channel:
            query = query.eq("fulfillment_channel", channel)
        if warehouse_id:
            query = query.eq("warehouse_id", warehouse_id)
        if sku:
            query = query.eq("sku", sku)

        response = (
            query.order("sku")
            .range(offset, offset + limit - 1)
            .execute()
        )

        items = response.data

        # Filter low stock if requested
        if low_stock:
            items = [
                item for item in items
                if item.get("reorder_point") and item["quantity"] <= item["reorder_point"]
            ]

        return {"inventory": items, "count": len(items)}
    except Exception as e:
        logger.error(f"Inventory fetch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ── Dynamic Inventory Analytics & ADS ─────────────────────────────────────

@router.get("/planner")
async def get_inventory_planner():
    """
    Get detailed inventory plan including 30-day ADS (Average Daily Sales), 
    Days of Stock, and Reorder Status.
    """
    try:
        now = datetime.now(timezone.utc)
        thirty_days_ago = (now - timedelta(days=30)).isoformat()
        
        # Get sales over last 30 days
        sales_resp = (
            supabase.table("order_items")
            .select("sku, quantity, orders!inner(purchase_date)")
            .gte("orders.purchase_date", thirty_days_ago)
            .execute()
        )
        
        # Calculate trailing 30 day sales per SKU
        sku_sales = {}
        for item in sales_resp.data:
            s_sku = item.get("sku")
            q = int(item.get("quantity") or 0)
            sku_sales[s_sku] = sku_sales.get(s_sku, 0) + q

        # Fetch inventory & sku info
        inv_query = (
            supabase.table("warehouse_inventory")
            .select("sku, quantity, sku_master(product_name, manufacturing_lead_time, transit_time)")
            .execute()
        )
        
        results = []
        # Aggregate totals per sku (combining warehouses)
        agg_inv = {}
        sku_metadata = {}
        for row in inv_query.data:
            sku = row["sku"]
            master = row.get("sku_master") or {}
            agg_inv[sku] = agg_inv.get(sku, 0) + int(row.get("quantity") or 0)
            sku_metadata[sku] = {
                "name": master.get("product_name"),
                "lead_time": int(master.get("manufacturing_lead_time") or 15),
                "transit_time": int(master.get("transit_time") or 15)
            }

        for sku, total_stock in agg_inv.items():
            sold_30d = sku_sales.get(sku, 0)
            ads = round(sold_30d / 30.0, 2)
            days_of_stock = int(total_stock / ads) if ads > 0 else 999
            
            meta = sku_metadata.get(sku, {})
            lead_time = meta.get("lead_time", 15)
            transit_time = meta.get("transit_time", 15)
            threshold = lead_time + transit_time
            
            if ads == 0 and total_stock == 0:
                status = "Out of Stock"
            elif days_of_stock <= threshold:
                status = "Restock Immediately"
            else:
                status = "Healthy"
                
            results.append({
                "sku": sku,
                "product_name": meta.get("name"),
                "available_stock": total_stock,
                "ads_30d": ads,
                "days_of_stock": days_of_stock,
                "reorder_status": status,
                "threshold_days": threshold
            })
            
        return {"inventory_plan": results}
    except Exception as e:
        logger.error(f"Planner error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ── FBM inventory management (manual) ─────────────────────────────────────

@router.post("/fbm")
async def add_fbm_inventory(
    sku: str,
    warehouse_id: str,
    warehouse_name: str = "Self-Fulfillment",
    quantity: int = 0,
):
    """
    Add or update FBM (self-fulfilled) inventory.
    FBA inventory is synced automatically; this endpoint is for manual FBM tracking.
    """
    try:
        row = {
            "sku": sku,
            "warehouse_id": warehouse_id,
            "warehouse_name": warehouse_name,
            "fulfillment_channel": "FBM",
            "quantity": quantity,
        }

        response = (
            supabase.table("warehouse_inventory")
            .upsert(row, on_conflict="sku,warehouse_id,fulfillment_channel")
            .execute()
        )

        return {
            "message": "FBM inventory updated",
            "data": response.data[0] if response.data else None,
        }
    except Exception as e:
        logger.error(f"FBM inventory error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
