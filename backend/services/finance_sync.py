"""
Finance sync service — fetches financial events from SP-API (FinancesV0)
and reconciles fee data into order_items.

This service:
1. Fetches financial events for a date range (or per-order)
2. Stores raw events in financial_events table
3. Aggregates fees per order-item and updates order_items fee columns
4. Recalculates net_profit using the snapshot unit_cogs
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from collections import defaultdict

from ..database import supabase
from . import sp_api_client

logger = logging.getLogger(__name__)

# ── Fee type mapping ────────────────────────────────────────────────────────
# Maps SP-API fee types to our order_items columns
FEE_COLUMN_MAP = {
    "Commission": "referral_fee",
    "RefurbishmentReferralFee": "referral_fee",
    "FBAPerUnitFulfillmentFee": "fba_fee",
    "FBAPerOrderFulfillmentFee": "fba_fee",
    "FBAWeightBasedFee": "fba_fee",
    "ShippingChargeback": "shipping_cost",
    "ShippingHB": "shipping_cost",
    # Everything else → other_fees
}


def sync_financial_events(
    days_back: int = 7,
    posted_after: Optional[str] = None,
    posted_before: Optional[str] = None,
) -> dict:
    """
    Sync financial events and reconcile fees into order_items.

    Args:
        days_back: Number of days to look back.
        posted_after: ISO datetime override.
        posted_before: ISO datetime upper bound.

    Returns:
        Summary dict.
    """
    start_time = time.time()
    stats = {
        "events_processed": 0,
        "events_stored": 0,
        "orders_reconciled": 0,
        "errors": [],
    }

    if not posted_after:
        since = datetime.now(timezone.utc) - timedelta(days=days_back)
        posted_after = since.isoformat()

    logger.info(f"Syncing financial events posted after {posted_after}")

    # ── 1. Fetch financial events (paginated) ───────────────────────────
    try:
        all_events = _fetch_all_financial_events(posted_after, posted_before)
    except Exception as e:
        logger.error(f"Failed to fetch financial events: {e}")
        stats["errors"].append(f"Finance fetch failed: {str(e)}")
        return _finalize(stats, start_time)

    logger.info(f"Raw financial event groups fetched")

    # ── 2. Process shipment events ──────────────────────────────────────
    # Accumulate fees per (amazon_order_id, order_item_id)
    fee_accumulator = defaultdict(lambda: defaultdict(float))

    for event in all_events:
        try:
            _store_and_accumulate(event, fee_accumulator, stats)
        except Exception as e:
            logger.error(f"Error processing financial event: {e}")
            stats["errors"].append(str(e))

    # ── 3. Reconcile fees into order_items ──────────────────────────────
    reconciled = _reconcile_fees(fee_accumulator, stats)
    stats["orders_reconciled"] = reconciled

    return _finalize(stats, start_time)


def sync_financial_events_for_order(amazon_order_id: str) -> dict:
    """
    Fetch and reconcile financial events for a single order.
    Useful after an order is synced to immediately get its fees.
    """
    start_time = time.time()
    stats = {
        "events_processed": 0,
        "events_stored": 0,
        "orders_reconciled": 0,
        "errors": [],
    }

    try:
        response = sp_api_client.get_financial_events_by_order(amazon_order_id)
        payload = response.payload.get("FinancialEvents", {})
    except Exception as e:
        logger.error(f"Failed to fetch financial events for {amazon_order_id}: {e}")
        stats["errors"].append(str(e))
        return _finalize(stats, start_time)

    fee_accumulator = defaultdict(lambda: defaultdict(float))

    # Process shipment events
    for shipment_event in payload.get("ShipmentEventList", []):
        _process_shipment_event(
            shipment_event, "ShipmentEvent", fee_accumulator, stats
        )

    # Process refund events
    for refund_event in payload.get("RefundEventList", []):
        _process_shipment_event(
            refund_event, "RefundEvent", fee_accumulator, stats
        )

    # Reconcile
    stats["orders_reconciled"] = _reconcile_fees(fee_accumulator, stats)

    return _finalize(stats, start_time)


def _fetch_all_financial_events(posted_after: str, posted_before: Optional[str]) -> list:
    """Fetch all financial event pages and flatten into event lists."""
    all_events = []
    next_token = None

    while True:
        try:
            response = sp_api_client.list_financial_events(
                posted_after=posted_after,
                posted_before=posted_before,
                next_token=next_token,
            )
        except Exception as e:
            logger.error(f"Error fetching financial events page: {e}")
            raise

        payload = response.payload.get("FinancialEvents", {})

        # Shipment events
        for event in payload.get("ShipmentEventList", []):
            all_events.append(("ShipmentEvent", event))

        # Refund events
        for event in payload.get("RefundEventList", []):
            all_events.append(("RefundEvent", event))

        next_token = response.payload.get("NextToken") or response.next_token
        if not next_token:
            break

        time.sleep(1.0)  # Rate limit

    return all_events


def _store_and_accumulate(event_tuple, fee_accumulator, stats):
    """Process a (event_type, event_data) tuple."""
    event_type, event_data = event_tuple
    _process_shipment_event(event_data, event_type, fee_accumulator, stats)


def _process_shipment_event(
    event_data: dict,
    event_type: str,
    fee_accumulator: dict,
    stats: dict,
):
    """Process a shipment/refund event and store individual fee lines."""
    amazon_order_id = event_data.get("AmazonOrderId", "")
    posted_date = event_data.get("PostedDate", "")

    for item_data in event_data.get("ShipmentItemList", event_data.get("ShipmentItemAdjustmentList", [])):
        order_item_id = item_data.get("OrderItemId", "")
        seller_sku = item_data.get("SellerSKU", "")

        # Process fee components
        for fee_item in item_data.get("ItemFeeList", []):
            _process_fee_line(
                amazon_order_id, order_item_id, event_type,
                fee_item, posted_date, fee_accumulator, stats,
            )

        # Process fee adjustments
        for fee_item in item_data.get("ItemFeeAdjustmentList", []):
            _process_fee_line(
                amazon_order_id, order_item_id, event_type,
                fee_item, posted_date, fee_accumulator, stats,
            )

        # Process charge components (item price, shipping, etc.)
        for charge_item in item_data.get("ItemChargeList", []):
            _process_charge_line(
                amazon_order_id, order_item_id, event_type,
                charge_item, posted_date, stats,
            )


def _process_fee_line(
    amazon_order_id: str,
    order_item_id: str,
    event_type: str,
    fee_item: dict,
    posted_date: str,
    fee_accumulator: dict,
    stats: dict,
):
    """Store a single fee line and accumulate it."""
    fee_type = fee_item.get("FeeType", "Unknown")
    amount = float(fee_item.get("FeeAmount", {}).get("CurrencyAmount", 0))
    currency = fee_item.get("FeeAmount", {}).get("CurrencyCode", "INR")

    if amount == 0:
        return

    stats["events_processed"] += 1

    # ── Store in financial_events ───────────────────────────────────────
    row = {
        "amazon_order_id": amazon_order_id,
        "order_item_id": order_item_id,
        "event_type": event_type,
        "fee_type": fee_type,
        "amount": amount,
        "currency_code": currency,
        "posted_date": posted_date,
    }

    try:
        supabase.table("financial_events").upsert(
            row,
            on_conflict="amazon_order_id,order_item_id,fee_type,posted_date",
        ).execute()
        stats["events_stored"] += 1
    except Exception as e:
        logger.warning(f"Failed to store financial event: {e}")

    # ── Accumulate for reconciliation ──────────────────────────────────
    # Fees from SP-API are negative (deductions), we store as positive values
    column = FEE_COLUMN_MAP.get(fee_type, "other_fees")
    key = (amazon_order_id, order_item_id)
    fee_accumulator[key][column] += abs(amount)


def _process_charge_line(
    amazon_order_id: str,
    order_item_id: str,
    event_type: str,
    charge_item: dict,
    posted_date: str,
    stats: dict,
):
    """Store charge lines (informational — not used for fee reconciliation)."""
    charge_type = charge_item.get("ChargeType", "Unknown")
    amount = float(charge_item.get("ChargeAmount", {}).get("CurrencyAmount", 0))

    if amount == 0:
        return

    row = {
        "amazon_order_id": amazon_order_id,
        "order_item_id": order_item_id,
        "event_type": event_type,
        "fee_type": f"CHARGE:{charge_type}",
        "amount": amount,
        "currency_code": charge_item.get("ChargeAmount", {}).get("CurrencyCode", "INR"),
        "posted_date": posted_date,
    }

    try:
        supabase.table("financial_events").upsert(
            row,
            on_conflict="amazon_order_id,order_item_id,fee_type,posted_date",
        ).execute()
    except Exception as e:
        logger.warning(f"Failed to store charge event: {e}")


def _reconcile_fees(fee_accumulator: dict, stats: dict) -> int:
    """
    Update order_items with accumulated fees and recalculate net_profit.
    Uses order_items.unit_cogs (snapshot) for profit calculation.
    """
    reconciled = 0

    for (amazon_order_id, order_item_id), fees in fee_accumulator.items():
        try:
            # Find the order in our database
            order_result = (
                supabase.table("orders")
                .select("id")
                .eq("amazon_order_id", amazon_order_id)
                .execute()
            )
            if not order_result.data:
                continue

            order_uuid = order_result.data[0]["id"]

            # Find the order item
            item_query = (
                supabase.table("order_items")
                .select("id, item_price, quantity, unit_cogs")
                .eq("order_id", order_uuid)
            )
            if order_item_id:
                item_query = item_query.eq("order_item_id", order_item_id)

            item_result = item_query.execute()

            if not item_result.data:
                continue

            for item in item_result.data:
                referral_fee = fees.get("referral_fee", 0)
                fba_fee = fees.get("fba_fee", 0)
                shipping_cost = fees.get("shipping_cost", 0)
                other_fees = fees.get("other_fees", 0)
                total_fees = referral_fee + fba_fee + other_fees

                # Recalculate profit using snapshot unit_cogs
                item_price = float(item.get("item_price", 0))
                unit_cogs = float(item.get("unit_cogs", 0))
                quantity = int(item.get("quantity", 1))
                cogs_total = unit_cogs * quantity

                net_profit = item_price - total_fees - shipping_cost - cogs_total
                margin_pct = (net_profit / item_price * 100) if item_price > 0 else 0

                supabase.table("order_items").update({
                    "referral_fee": round(referral_fee, 2),
                    "fba_fee": round(fba_fee, 2),
                    "shipping_cost": round(shipping_cost, 2),
                    "other_fees": round(other_fees, 2),
                    "total_fees": round(total_fees, 2),
                    "cogs_total": round(cogs_total, 2),
                    "net_profit": round(net_profit, 2),
                    "profit_margin_pct": round(margin_pct, 2),
                }).eq("id", item["id"]).execute()

                reconciled += 1

        except Exception as e:
            logger.error(f"Error reconciling fees for {amazon_order_id}: {e}")
            stats["errors"].append(f"Reconcile {amazon_order_id}: {str(e)}")

    return reconciled


def _finalize(stats: dict, start_time: float) -> dict:
    """Add duration and log summary."""
    stats["duration_seconds"] = round(time.time() - start_time, 2)
    logger.info(
        f"Finance sync complete: {stats['events_processed']} events, "
        f"{stats['events_stored']} stored, {stats['orders_reconciled']} reconciled, "
        f"{len(stats['errors'])} errors in {stats['duration_seconds']}s"
    )
    return stats
