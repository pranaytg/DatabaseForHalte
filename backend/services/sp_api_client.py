"""
Amazon SP-API client wrapper with exponential backoff and rate-limit handling.

Uses the python-amazon-sp-api library under the hood, wrapped with
tenacity-based retries to stay within free-tier SP-API rate limits.
"""

import logging
import time
from typing import Optional
from functools import wraps

from sp_api.api import (
    Orders,
    Inventories,
    Finances,
    CatalogItemsV20220401 as CatalogItems,
)
from sp_api.base import Marketplaces, ApiResponse
from sp_api.base.exceptions import SellingApiRequestThrottledException

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from ..config import settings

logger = logging.getLogger(__name__)

# ── Rate-limit-aware retry decorator ────────────────────────────────────────
# SP-API free tier is very strict: ~1 req/sec on most endpoints.
# We use exponential backoff starting at 2s, capping at 60s, max 6 attempts.

sp_api_retry = retry(
    retry=retry_if_exception_type(SellingApiRequestThrottledException),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    stop=stop_after_attempt(6),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


def _get_credentials() -> dict:
    """Build the credentials dict for python-amazon-sp-api."""
    return {
        "lwa_app_id": settings.sp_api_lwa_app_id,
        "lwa_client_secret": settings.sp_api_lwa_client_secret,
        "refresh_token": settings.sp_api_refresh_token,
    }


# ── Orders API ──────────────────────────────────────────────────────────────

@sp_api_retry
def get_orders(
    created_after: str,
    created_before: Optional[str] = None,
    order_statuses: Optional[list] = None,
    next_token: Optional[str] = None,
) -> ApiResponse:
    """
    Fetch orders from SP-API OrdersV0.
    Handles pagination via next_token.
    """
    client = Orders(credentials=_get_credentials(), marketplace=Marketplaces.IN)

    kwargs = {
        "MarketplaceIds": [settings.sp_api_marketplace_id],
    }
    # Amazon rejects requests that have BOTH CreatedAfter AND NextToken
    if next_token:
        kwargs["NextToken"] = next_token
    else:
        kwargs["CreatedAfter"] = created_after
    if created_before:
        kwargs["CreatedBefore"] = created_before
    if order_statuses:
        kwargs["OrderStatuses"] = order_statuses

    response = client.get_orders(**kwargs)
    logger.info(f"Fetched {len(response.payload.get('Orders', []))} orders")
    return response


@sp_api_retry
def get_order_items(amazon_order_id: str) -> ApiResponse:
    """Fetch line items for a specific order."""
    client = Orders(credentials=_get_credentials(), marketplace=Marketplaces.IN)
    response = client.get_order_items(order_id=amazon_order_id)
    logger.info(
        f"Fetched {len(response.payload.get('OrderItems', []))} items "
        f"for order {amazon_order_id}"
    )
    return response


# ── FBA Inventory API ───────────────────────────────────────────────────────

@sp_api_retry
def get_fba_inventory(
    next_token: Optional[str] = None,
) -> ApiResponse:
    """
    Fetch FBA inventory summaries.
    Returns per-SKU sellable/inbound/reserved/unfulfillable quantities.
    """
    client = Inventories(credentials=_get_credentials(), marketplace=Marketplaces.IN)

    kwargs = {
        "details": True,
        "marketplaceIds": [settings.sp_api_marketplace_id],
    }
    if next_token:
        kwargs["nextToken"] = next_token

    response = client.get_inventory_summary_marketplace(**kwargs)
    summaries = response.payload.get("inventorySummaries", [])
    logger.info(f"Fetched {len(summaries)} inventory summaries")
    return response


# ── Finances API ────────────────────────────────────────────────────────────

@sp_api_retry
def get_financial_events_by_order(amazon_order_id: str) -> ApiResponse:
    """Fetch all financial events for a specific order."""
    client = Finances(credentials=_get_credentials(), marketplace=Marketplaces.IN)
    response = client.get_financial_events_for_order(order_id=amazon_order_id)
    logger.info(f"Fetched financial events for order {amazon_order_id}")
    return response


@sp_api_retry
def list_financial_events(
    posted_after: str,
    posted_before: Optional[str] = None,
    next_token: Optional[str] = None,
) -> ApiResponse:
    """
    List financial events within a date range.
    Used for bulk reconciliation of fees.
    """
    client = Finances(credentials=_get_credentials(), marketplace=Marketplaces.IN)

    kwargs = {"PostedAfter": posted_after}
    if posted_before:
        kwargs["PostedBefore"] = posted_before
    if next_token:
        kwargs["NextToken"] = next_token

    response = client.list_financial_events(**kwargs)
    logger.info("Fetched financial events page")
    return response


# ── Catalog Items (optional — for enriching sku_master) ─────────────────────

@sp_api_retry
def get_catalog_item(asin: str) -> ApiResponse:
    """Fetch catalog details for a single ASIN (dimensions, attributes, productTypes)."""
    client = CatalogItems(credentials=_get_credentials(), marketplace=Marketplaces.IN)
    response = client.get_catalog_item(
        asin=asin,
        marketplaceIds=["A21TJRUUN4KGV"],
        includedData=["dimensions", "attributes", "productTypes"]
    )
    logger.info(f"Fetched catalog item for ASIN {asin}")
    return response


# ── Helper: paginated fetch ─────────────────────────────────────────────────

def fetch_all_pages(fetcher_fn, payload_key: str, **kwargs) -> list:
    """
    Generic paginator — keeps fetching until no NextToken.
    Adds a 1-second sleep between pages to stay within rate limits.

    Args:
        fetcher_fn: One of the SP-API functions above.
        payload_key: Key in the response payload containing the list items.
        **kwargs: Arguments to pass to fetcher_fn.

    Returns:
        Flat list of all items across all pages.
    """
    all_items = []
    next_token = None

    while True:
        if next_token:
            kwargs["next_token"] = next_token

        response = fetcher_fn(**kwargs)
        items = response.payload.get(payload_key, [])
        all_items.extend(items)

        next_token = response.payload.get("NextToken") or response.next_token
        if not next_token:
            break

        # Rate-limit courtesy sleep between pages
        time.sleep(1.0)
        logger.debug(f"Paginating... {len(all_items)} items so far")

    logger.info(f"Total items fetched: {len(all_items)}")
    return all_items
