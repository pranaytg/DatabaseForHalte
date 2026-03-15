"""
Inventory router — warehouse inventory views and FBM stock management.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
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
