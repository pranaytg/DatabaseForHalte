"""
Amazon SP-API Dashboard — FastAPI Backend

Entry point: uvicorn backend.main:app --reload
"""

import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import dashboard, inventory, profitability, sync, shipping
from .tasks.scheduler import init_scheduler, shutdown_scheduler

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-25s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Lifespan ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup & shutdown logic."""
    logger.info("Starting Amazon SP-API Dashboard Backend")

    # Validate SP-API credentials at startup
    from .services.lwa_auth import validate_credentials
    cred_status = validate_credentials()
    if cred_status["token_valid"]:
        logger.info("✓ SP-API credentials validated — LWA token acquired")
    elif cred_status["error"]:
        logger.warning(f"⚠ SP-API credential issue: {cred_status['error']}")
    else:
        logger.warning("⚠ SP-API credentials not fully configured")

    # Start scheduler if not in dev/test mode
    if os.getenv("DISABLE_SCHEDULER") != "true":
        init_scheduler()
        logger.info("Background scheduler started")
    else:
        logger.info("Scheduler disabled (DISABLE_SCHEDULER=true)")

    yield

    # Shutdown
    shutdown_scheduler()
    logger.info("Backend shut down cleanly")


# ── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Amazon SP-API Dashboard",
    description="Sales Dashboard, Inventory Management, Shipment Calculator, Profitability Tracker",
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS ────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ───────────────────────────────────────────────────────

app.include_router(dashboard.router)
app.include_router(inventory.router)
app.include_router(profitability.router)
app.include_router(sync.router)
app.include_router(shipping.router)


# ── Health check ────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def health_check():
    """Health check endpoint — also serves as keep-alive target."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "2.0.0",
        "service": "amazon-sp-api-dashboard",
    }


@app.get("/api/health", tags=["Health"])
async def detailed_health():
    """Detailed health check with database and config status."""
    from .database import supabase

    db_ok = False
    try:
        result = supabase.table("sku_master").select("sku", count="exact").limit(1).execute()
        db_ok = True
        sku_count = result.count or 0
    except Exception as e:
        sku_count = 0
        logger.warning(f"Database health check failed: {e}")

    sp_api_configured = bool(
        settings.sp_api_lwa_app_id
        and settings.sp_api_lwa_client_secret
        and settings.sp_api_refresh_token
    )

    return {
        "status": "healthy" if db_ok else "degraded",
        "database": {"connected": db_ok, "sku_count": sku_count},
        "sp_api": {"configured": sp_api_configured},
        "scheduler": {"enabled": os.getenv("DISABLE_SCHEDULER") != "true"},
    }


# ── Run with uvicorn ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
