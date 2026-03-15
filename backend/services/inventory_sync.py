"""
Inventory sync service — fetches FBA inventory from SP-API and upserts
into the warehouse_inventory table.

This service:
1. Fetches all FBA inventory summaries (paginated)
2. Upserts per-SKU, per-warehouse rows
3. Marks stale rows (not updated this cycle) as zero quantity
"""

import logging
import time
from datetime import datetime, timezone

from ..database import supabase
from . import sp_api_client

logger = logging.getLogger(__name__)


def sync_inventory() -> dict:
    """
    Sync FBA inventory from SP-API into warehouse_inventory table.

    Returns:
        Summary dict with counts.
    """
    start_time = time.time()
    stats = {
        "records_processed": 0,
        "records_created": 0,
        "records_updated": 0,
        "errors": [],
    }

    # ── 1. Fetch all inventory summaries (paginated) ────────────────────
    try:
        summaries = sp_api_client.fetch_all_pages(
            sp_api_client.get_fba_inventory,
            payload_key="inventorySummaries",
        )
    except Exception as e:
        logger.error(f"Failed to fetch inventory: {e}")
        stats["errors"].append(f"Inventory fetch failed: {str(e)}")
        return _finalize(stats, start_time)

    logger.info(f"Fetched {len(summaries)} inventory summaries")

    now = datetime.now(timezone.utc).isoformat()
    synced_keys = set()  # track (sku, warehouse_id, channel) we've seen

    # ── 2. Upsert each summary ─────────────────────────────────────────
    for summary in summaries:
        try:
            _process_inventory_summary(summary, now, stats, synced_keys)
        except Exception as e:
            sku = summary.get("sellerSku", "unknown")
            logger.error(f"Error processing inventory for {sku}: {e}")
            stats["errors"].append(f"SKU {sku}: {str(e)}")

    # ── 3. Mark stale inventory as zero (optional — disabled by default) ─
    # Uncomment if you want to zero-out SKUs not returned by SP-API:
    # _zero_stale_inventory(synced_keys, now)

    return _finalize(stats, start_time)


def _process_inventory_summary(
    summary: dict,
    sync_time: str,
    stats: dict,
    synced_keys: set,
):
    """Process a single FBA inventory summary."""
    stats["records_processed"] += 1

    sku = summary.get("sellerSku", "")
    asin = summary.get("asin", "")
    fnsku = summary.get("fnSku", "")
    product_name = summary.get("productName", f"Unknown ({sku})")
    condition = summary.get("condition", "NewItem")

    # Inventory details
    inv_details = summary.get("inventoryDetails", {})
    fulfillable = inv_details.get("fulfillableQuantity", 0)
    inbound_working = inv_details.get("inboundWorkingQuantity", 0)
    inbound_shipped = inv_details.get("inboundShippedQuantity", 0)
    inbound_receiving = inv_details.get("inboundReceivingQuantity", 0)
    total_inbound = inbound_working + inbound_shipped + inbound_receiving

    # Reserved & unfulfillable
    reserved_details = inv_details.get("reservedQuantity", {})
    reserved = (
        reserved_details.get("totalReservedQuantity", 0)
        if isinstance(reserved_details, dict) else 0
    )

    unfulfillable_details = inv_details.get("unfulfillableQuantity", {})
    unfulfillable = (
        unfulfillable_details.get("totalUnfulfillableQuantity", 0)
        if isinstance(unfulfillable_details, dict) else 0
    )

    # Warehouse / granularity
    # SP-API returns marketplace-level granularity; we use marketplace as "warehouse"
    warehouse_id = "FBA-IN"  # Amazon.in FBA network
    warehouse_name = "Amazon FBA India"

    # ── Ensure SKU exists in sku_master ─────────────────────────────────
    _ensure_sku_exists(sku, asin, fnsku, product_name)

    # ── Upsert inventory row ───────────────────────────────────────────
    row = {
        "sku": sku,
        "warehouse_id": warehouse_id,
        "warehouse_name": warehouse_name,
        "fulfillment_channel": "FBA",
        "quantity": fulfillable,
        "quantity_inbound": total_inbound,
        "quantity_reserved": reserved,
        "quantity_unfulfillable": unfulfillable,
        "last_synced_at": sync_time,
    }

    result = (
        supabase.table("warehouse_inventory")
        .upsert(row, on_conflict="sku,warehouse_id,fulfillment_channel")
        .execute()
    )

    if result.data:
        db_row = result.data[0]
        if db_row.get("created_at") == db_row.get("updated_at"):
            stats["records_created"] += 1
        else:
            stats["records_updated"] += 1

    synced_keys.add((sku, warehouse_id, "FBA"))


def _ensure_sku_exists(sku: str, asin: str, fnsku: str, product_name: str):
    """Auto-create sku_master entry if it doesn't exist."""
    existing = (
        supabase.table("sku_master")
        .select("sku")
        .eq("sku", sku)
        .execute()
    )
    if not existing.data:
        supabase.table("sku_master").insert({
            "sku": sku,
            "asin": asin,
            "fnsku": fnsku,
            "product_name": product_name or f"Auto-created: {sku}",
            "cogs": 0.0,
            "channel": "amazon",
        }).execute()
        logger.info(f"Auto-created sku_master entry for {sku}")
    else:
        # Update FNSKU if we have it now and didn't before
        if fnsku:
            supabase.table("sku_master").update({
                "fnsku": fnsku,
            }).eq("sku", sku).execute()


def _finalize(stats: dict, start_time: float) -> dict:
    """Add duration and log summary."""
    stats["duration_seconds"] = round(time.time() - start_time, 2)
    logger.info(
        f"Inventory sync complete: {stats['records_processed']} processed, "
        f"{stats['records_created']} created, {stats['records_updated']} updated, "
        f"{len(stats['errors'])} errors in {stats['duration_seconds']}s"
    )
    return stats
