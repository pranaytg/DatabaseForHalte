"""
Order sync service — fetches orders from SP-API and upserts into Supabase.

This service:
1. Fetches orders from Amazon SP-API (OrdersV0)
2. For each order, fetches line items (OrderItems)
3. Looks up COGS from sku_master and snapshots it into order_items.unit_cogs
4. Calculates profitability per line item
5. Upserts everything into the database
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from ..database import supabase
from . import sp_api_client

logger = logging.getLogger(__name__)


def sync_orders(
    days_back: int = 7,
    created_after: Optional[str] = None,
    created_before: Optional[str] = None,
) -> dict:
    """
    Sync orders from SP-API into the database.

    Args:
        days_back: Number of days to look back (default 7, for cron jobs).
        created_after: ISO datetime override (takes precedence over days_back).
        created_before: ISO datetime upper bound (optional).

    Returns:
        Summary dict with counts of processed/created/updated/errors.
    """
    start_time = time.time()
    stats = {
        "orders_processed": 0,
        "orders_created": 0,
        "orders_updated": 0,
        "items_created": 0,
        "errors": [],
    }

    # ── 1. Determine date range ─────────────────────────────────────────────
    if not created_after:
        since = datetime.now(timezone.utc) - timedelta(days=days_back)
        created_after = since.isoformat()

    logger.info(f"Syncing orders created after {created_after}")

    # ── 2. Pre-load COGS lookup from sku_master ─────────────────────────────
    cogs_lookup = _load_cogs_lookup()

    # ── 3. Fetch all orders (paginated) ─────────────────────────────────────
    try:
        all_orders = sp_api_client.fetch_all_pages(
            sp_api_client.get_orders,
            payload_key="Orders",
            created_after=created_after,
            created_before=created_before,
        )
    except Exception as e:
        logger.error(f"Failed to fetch orders: {e}")
        stats["errors"].append(f"Order fetch failed: {str(e)}")
        return _finalize(stats, start_time)

    logger.info(f"Fetched {len(all_orders)} orders from SP-API")

    # ── 4. Process each order ───────────────────────────────────────────────
    for order_data in all_orders:
        try:
            _process_order(order_data, cogs_lookup, stats)
        except Exception as e:
            order_id = order_data.get("AmazonOrderId", "unknown")
            logger.error(f"Error processing order {order_id}: {e}")
            stats["errors"].append(f"Order {order_id}: {str(e)}")

    return _finalize(stats, start_time)


def _load_cogs_lookup() -> dict:
    """Load SKU → COGS mapping from sku_master."""
    response = supabase.table("sku_master").select("sku, cogs").execute()
    return {row["sku"]: float(row["cogs"]) for row in response.data}


def _process_order(order_data: dict, cogs_lookup: dict, stats: dict):
    """Process a single order — upsert header + items."""
    amazon_order_id = order_data["AmazonOrderId"]
    stats["orders_processed"] += 1

    # ── Determine fulfillment channel ───────────────────────────────────
    fc_raw = order_data.get("FulfillmentChannel", "MFN")
    fulfillment_channel = "FBA" if fc_raw == "AFN" else "FBM"

    # ── Parse order total ───────────────────────────────────────────────
    order_total = 0.0
    if order_data.get("OrderTotal"):
        order_total = float(order_data["OrderTotal"].get("Amount", 0))

    # ── Map status ──────────────────────────────────────────────────────
    status_map = {
        "Pending": "Pending",
        "Unshipped": "Unshipped",
        "PartiallyShipped": "PartiallyShipped",
        "Shipped": "Shipped",
        "Canceled": "Canceled",
        "Unfulfillable": "Canceled",
    }
    order_status = status_map.get(
        order_data.get("OrderStatus", "Pending"), "Pending"
    )

    # ── Build order row ─────────────────────────────────────────────────
    order_row = {
        "amazon_order_id": amazon_order_id,
        "purchase_date": order_data.get("PurchaseDate"),
        "last_update_date": order_data.get("LastUpdateDate"),
        "order_status": order_status,
        "fulfillment_channel": fulfillment_channel,
        "order_total": order_total,
        "currency_code": order_data.get("OrderTotal", {}).get("CurrencyCode", "INR"),
        "buyer_name": order_data.get("BuyerInfo", {}).get("BuyerName"),
        "shipping_city": order_data.get("ShippingAddress", {}).get("City"),
        "shipping_state": order_data.get("ShippingAddress", {}).get("StateOrRegion"),
        "shipping_postal_code": order_data.get("ShippingAddress", {}).get("PostalCode"),
        "marketplace_id": order_data.get("MarketplaceId", "A21TJRUUN4KGV"),
        "sales_channel": order_data.get("SalesChannel", "Amazon.in"),
    }

    # ── Upsert order ────────────────────────────────────────────────────
    result = (
        supabase.table("orders")
        .upsert(order_row, on_conflict="amazon_order_id")
        .execute()
    )

    if result.data:
        db_order = result.data[0]
        order_uuid = db_order["id"]

        # Check if this was a new insert or update
        if db_order.get("created_at") == db_order.get("updated_at"):
            stats["orders_created"] += 1
        else:
            stats["orders_updated"] += 1
    else:
        logger.warning(f"No data returned for order upsert: {amazon_order_id}")
        return

    # ── Fetch and process order items ───────────────────────────────────
    # Rate-limit: small sleep before fetching items
    time.sleep(0.5)

    try:
        items_response = sp_api_client.get_order_items(amazon_order_id)
        order_items = items_response.payload.get("OrderItems", [])
    except Exception as e:
        logger.error(f"Failed to fetch items for {amazon_order_id}: {e}")
        stats["errors"].append(f"Items for {amazon_order_id}: {str(e)}")
        return

    for item_data in order_items:
        _process_order_item(item_data, order_uuid, cogs_lookup, stats)


def _process_order_item(
    item_data: dict,
    order_uuid: str,
    cogs_lookup: dict,
    stats: dict,
):
    """Process a single order line item — upsert with COGS snapshot."""
    sku = item_data.get("SellerSKU", "UNKNOWN")
    quantity = int(item_data.get("QuantityOrdered", 1))

    # ── Parse money fields ──────────────────────────────────────────────
    item_price = _parse_money(item_data.get("ItemPrice"))
    item_tax = _parse_money(item_data.get("ItemTax"))
    shipping_price = _parse_money(item_data.get("ShippingPrice"))
    shipping_tax = _parse_money(item_data.get("ShippingTax"))
    promotion_discount = _parse_money(item_data.get("PromotionDiscount"))

    # ── COGS snapshot: freeze the current COGS at sync time ─────────────
    unit_cogs = cogs_lookup.get(sku, 0.0)

    # ── Calculate profitability (fees will be updated later from Finances)
    cogs_total = unit_cogs * quantity
    # Fees not yet known at order sync time; will be populated by finance sync
    total_fees = 0.0
    shipping_cost = 0.0
    net_profit = item_price - total_fees - shipping_cost - cogs_total
    margin_pct = (net_profit / item_price * 100) if item_price > 0 else 0.0

    # ── Ensure SKU exists in sku_master (auto-create if missing) ────────
    _ensure_sku_exists(sku, item_data.get("ASIN"))

    item_row = {
        "order_id": order_uuid,
        "sku": sku,
        "asin": item_data.get("ASIN"),
        "order_item_id": item_data.get("OrderItemId"),
        "quantity": quantity,
        "item_price": item_price,
        "item_tax": item_tax,
        "shipping_price": shipping_price,
        "shipping_tax": shipping_tax,
        "promotion_discount": promotion_discount,
        "unit_cogs": unit_cogs,
        "cogs_total": round(cogs_total, 2),
        "shipping_cost": round(shipping_cost, 2),
        "total_fees": round(total_fees, 2),
        "net_profit": round(net_profit, 2),
        "profit_margin_pct": round(margin_pct, 2),
    }

    supabase.table("order_items").upsert(
        item_row,
        on_conflict="order_id,order_item_id",
    ).execute()

    stats["items_created"] += 1


def _ensure_sku_exists(sku: str, asin: Optional[str] = None):
    """Auto-create a sku_master row if the SKU doesn't exist yet."""
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
            "product_name": f"Auto-created: {sku}",
            "cogs": 0.0,
            "channel": "amazon",
        }).execute()
        logger.info(f"Auto-created sku_master entry for {sku}")


def _parse_money(money_obj: Optional[dict]) -> float:
    """Extract Amount from an SP-API Money object, default 0."""
    if not money_obj:
        return 0.0
    return float(money_obj.get("Amount", 0))


def _finalize(stats: dict, start_time: float) -> dict:
    """Add duration and log summary."""
    stats["duration_seconds"] = round(time.time() - start_time, 2)
    logger.info(
        f"Order sync complete: {stats['orders_processed']} processed, "
        f"{stats['orders_created']} created, {stats['orders_updated']} updated, "
        f"{stats['items_created']} items, {len(stats['errors'])} errors "
        f"in {stats['duration_seconds']}s"
    )
    return stats
