import asyncio
import os
import sys
import logging

# Add the project directory to the path so we can import backend packages
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.config import settings
from backend.services.lwa_auth import validate_credentials
from backend.services.dimensions_sync import sync_dimensions_batch

# Configure terminal logging to be highly visible
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("force_sync_dimensions")

def run_sync():
    logger.info("🚀 Starting Manual Force Sync: SP-API Dimensions")
    
    # 1. Initialize Auth
    logger.info("🔑 Validating LWA Authentication...")
    auth_status = validate_credentials()
    if not auth_status.get("token_valid"):
        logger.error(f"❌ Authentication failed: {auth_status.get('error')}")
        logger.error("Please verify your SP-API credentials in .env")
        return
        
    logger.info("✅ Authentication successful. Proceeding to batch sync.")
    logger.info("-" * 60)

    # 3. Execute Real-Time Batch Sync
    logger.info("📏 Step 1: Running Real-Time Dimensions Sync...")
    try:
        # Pass a high limit so it processes everything needing dimensions
        stats = sync_dimensions_batch(limit=500)
        logger.info("-" * 60)
        logger.info(f"✨ Dimensions Force Sync Complete!")
        logger.info(f"📊 Processed: {stats['processed']} | Updated: {stats['updated']} | Errors: {len(stats['errors'])}")
        
        if stats['errors']:
            logger.warning("Errors encountered:")
            for err in stats['errors']:
                logger.warning(f"  - {err}")
                
    except Exception as e:
        logger.error(f"❌ Critical error during dimensions sync: {e}")

if __name__ == "__main__":
    run_sync()
