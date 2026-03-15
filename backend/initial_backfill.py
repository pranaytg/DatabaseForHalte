import asyncio
from datetime import datetime, timedelta
import logging

from backend.config import settings
from backend.services.lwa_auth import validate_credentials
from backend.services.inventory_sync import sync_fba_inventory
from backend.services.order_sync import sync_recent_orders
from backend.services.finance_sync import sync_recent_financial_events

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("initial_backfill")

async def run_backfill(days=30):
    logger.info(f"🚀 Starting Initial Historical Backfill ({days} days)")
    
    # 1. Initialize Auth
    logger.info("🔑 Initializing LWA Authentication...")
    auth_status = validate_credentials()
    if not auth_status.get("token_valid"):
        logger.error(f"❌ Authentication failed: {auth_status.get('error')}")
        return
    logger.info("✅ Authentication successful.")

    # 2. Sequence 1: Catalog & Inventory
    logger.info("\n📦 SEQUENCE 1: Fetching Inventory & Populating SKU Catalog")
    logger.info("This ensures all SKUs exist in sku_master before syncing orders.")
    try:
        # FBA Inventory API doesn't take a date range, it just returns current snapshot
        result = await sync_fba_inventory()
        logger.info(f"✅ Inventory Sync Complete: {result.get('message')}")
    except Exception as e:
        logger.error(f"❌ Inventory Sync failed: {e}")
        logger.warning("Continuing to orders, but foreign key errors may occur if SKUs are missing.")

    # 3. Sequence 2: Historical Orders
    logger.info(f"\n🛒 SEQUENCE 2: Fetching Historical Orders (Last {days} days)")
    created_after = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"
    try:
        # The underlying sync_recent_orders uses sp_api_client which uses OrdersV0.get_orders
        # Because we want a full backfill, we pass the custom date
        result = await sync_recent_orders(created_after=created_after)
        logger.info(f"✅ Order Sync Complete: {result.get('message')} - Inserted/Updated: {result.get('orders_synced')}")
    except Exception as e:
        logger.error(f"❌ Order Sync failed: {e}")
        logger.error("Stopping backfill as finance sync depends on orders.")
        return

    # 4. Sequence 3: Historical Finances
    logger.info(f"\n💰 SEQUENCE 3: Fetching Financial Events (Last {days} days)")
    posted_after = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"
    try:
        result = await sync_recent_financial_events(posted_after=posted_after)
        logger.info(f"✅ Finance Sync Complete: {result.get('message')}")
    except Exception as e:
        logger.error(f"❌ Finance Sync failed: {e}")

    logger.info("\n✨ Initial Historical Backfill Completed Successfully!")

if __name__ == "__main__":
    # Ensure environment variables are loaded if not using Docker/Uvicorn
    from dotenv import load_dotenv
    load_dotenv()
    
    # Run the backfill, defaulting to 30 days
    asyncio.run(run_backfill(days=30))
