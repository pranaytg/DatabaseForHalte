import os
import sys
import logging
import time
from datetime import datetime, timedelta, timezone

# Add the project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import supabase
from backend.services.lwa_auth import validate_credentials
from backend.services import sp_api_client

# Configure logging to be highly visible
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("force_sync_orders")

def run_sync():
    logger.info("🚀 Starting Manual Force Sync: SP-API Orders (Last 30 Days)")
    
    # 1. Initialize Auth
    logger.info("🔑 Validating LWA Authentication...")
    auth_status = validate_credentials()
    if not auth_status.get("token_valid"):
        logger.error(f"❌ Authentication failed: {auth_status.get('error')}")
        logger.error("Please verify your SP-API credentials in .env")
        return
        
    logger.info("✅ Authentication successful.")
    logger.info("-" * 60)
    
    # 2. Get COGS Lookup
    logger.info("📦 Loading COGS mapping from sku_master...")
    response = supabase.table("sku_master").select("sku, cogs").execute()
    cogs_lookup = {row["sku"]: float(row["cogs"] if row["cogs"] is not None else 0.0) for row in response.data}
    logger.info(f"Loaded {len(cogs_lookup)} SKUs with COGS data.")
    
    # 3. Fetch Orders
    created_after_dt = datetime.now(timezone.utc) - timedelta(days=30)
    created_after = created_after_dt.isoformat().replace("+00:00", "Z")
    logger.info(f"📅 Fetching orders created after: {created_after}")
    
    try:
        all_orders = sp_api_client.fetch_all_pages(
            sp_api_client.get_orders,
            payload_key="Orders",
            created_after=created_after,
        )
    except Exception as e:
        logger.error(f"❌ Failed to fetch orders stream: {e}")
        return
        
    logger.info(f"✅ Downloaded {len(all_orders)} orders. Starting individual item sync...")
    logger.info("-" * 60)
    
    # 4. Process Each Order
    for order_data in all_orders:
        amazon_order_id = order_data["AmazonOrderId"]
        
        # Determine FC
        fc_raw = order_data.get("FulfillmentChannel", "MFN")
        fulfillment_channel = "FBA" if fc_raw == "AFN" else "FBM"
        
        # Order Total
        order_total = 0.0
        if order_data.get("OrderTotal"):
            order_total = float(order_data["OrderTotal"].get("Amount", 0))
            
        # Status Map
        status_map = {
            "Pending": "Pending", "Unshipped": "Unshipped",
            "PartiallyShipped": "PartiallyShipped", "Shipped": "Shipped",
            "Canceled": "Canceled", "Unfulfillable": "Canceled"
        }
        order_status = status_map.get(order_data.get("OrderStatus", "Pending"), "Pending")
        
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
        
        # Upsert Order
        res = supabase.table("orders").upsert(order_row, on_conflict="amazon_order_id").execute()
        if not res.data:
            logger.error(f"Failed to upsert order {amazon_order_id}")
            continue
        order_uuid = res.data[0]["id"]
        
        # Strict sleep before fetching order items to avoid SP-API 429 Too Many Requests
        time.sleep(1.5) 
        try:
            items_res = sp_api_client.get_order_items(amazon_order_id)
            order_items = items_res.payload.get("OrderItems", [])
        except Exception as e:
            logger.error(f"❌ Failed extracting items for {amazon_order_id}: {e}")
            continue
            
        locked_cogs_sum = 0.0
        used_fallback = False
        
        for item in order_items:
            sku = item.get("SellerSKU", "UNKNOWN")
            qty = int(item.get("QuantityOrdered", 1))
            
            def parse_money(m): return float(m.get("Amount", 0)) if m else 0.0
            
            item_price = parse_money(item.get("ItemPrice"))
            item_tax = parse_money(item.get("ItemTax"))
            shipping_price = parse_money(item.get("ShippingPrice"))
            shipping_tax = parse_money(item.get("ShippingTax"))
            promotion_discount = parse_money(item.get("PromotionDiscount"))
            
            unit_cogs = cogs_lookup.get(sku, 0.0)
            
            # --- DYNAMIC COGS FALLBACK LOGIC ---
            if unit_cogs <= 0.0:
                unit_cogs = round(item_price * 0.50, 2)
                used_fallback = True
                
            cogs_total = unit_cogs * qty
            locked_cogs_sum += cogs_total
            
            # Make sure SKU exists in DB before linking
            existing = supabase.table("sku_master").select("sku").eq("sku", sku).execute()
            if not existing.data:
                supabase.table("sku_master").insert({
                    "sku": sku,
                    "asin": item.get("ASIN"),
                    "product_name": f"Auto-created: {sku}",
                    "cogs": 0.0,
                    "channel": "amazon",
                }).execute()
            
            item_row = {
                "order_id": order_uuid,
                "sku": sku,
                "asin": item.get("ASIN"),
                "order_item_id": item.get("OrderItemId"),
                "quantity": qty,
                "item_price": item_price,
                "item_tax": item_tax,
                "shipping_price": shipping_price,
                "shipping_tax": shipping_tax,
                "promotion_discount": promotion_discount,
                "unit_cogs": unit_cogs,
                "cogs_total": round(cogs_total, 2),
                "shipping_cost": 0.0,
                "total_fees": 0.0,
                "net_profit": round(item_price - cogs_total, 2),
                "profit_margin_pct": round(((item_price - cogs_total) / item_price * 100) if item_price > 0 else 0.0, 2),
            }
            supabase.table("order_items").upsert(item_row, on_conflict="order_item_id").execute()
            
        cogs_source = "50% Fallback" if used_fallback else "Database"
        logger.info(f"[SUCCESS] Inserted Order {amazon_order_id} with {len(order_items)} items. COGS locked at ₹{locked_cogs_sum:.2f} ({cogs_source})")
        
    logger.info("✅ Orders Sync Complete!")

if __name__ == "__main__":
    run_sync()
