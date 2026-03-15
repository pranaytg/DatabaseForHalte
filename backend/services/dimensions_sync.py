"""
Dimensions sync service — fetches actual package dimensions from SP-API
Catalog Items API and stores them in `sku_master` for localized shipping calculations.
"""

import logging
import time
from typing import Dict, Optional, Tuple

from ..database import supabase
from . import sp_api_client

logger = logging.getLogger(__name__)

def parse_dimension_value(dim_obj: Optional[Dict]) -> float:
    if not dim_obj:
        return 0.0
    value = dim_obj.get("value", 0.0)
    unit = dim_obj.get("unit", "").lower()

    if unit in ["inches", "inch", "in"]:
        return round(value * 2.54, 2)
    elif unit in ["centimeters", "centimeter", "cm"]:
        return round(value, 2)
    elif unit in ["millimeters", "millimeter", "mm"]:
        return round(value / 10.0, 2)
    
    # Default fallback if unit isn't matched
    return round(value, 2)

def parse_weight_value(weight_obj: Optional[Dict]) -> float:
    if not weight_obj:
        return 0.0
    value = weight_obj.get("value", 0.0)
    unit = weight_obj.get("unit", "").lower()

    if unit in ["pounds", "pound", "lbs", "lb"]:
        return round(value * 0.453592, 3)
    elif unit in ["ounces", "ounce", "oz"]:
        return round(value * 0.0283495, 3)
    elif unit in ["grams", "gram", "g"]:
        return round(value / 1000.0, 3)
    elif unit in ["kilograms", "kilogram", "kg"]:
        return round(value, 3)
        
    return round(value, 3)

def extract_package_dimensions(dimensions_list: list) -> Tuple[float, float, float, float]:
    """Extracts (length, width, height, weight) in cm and kg from SP-API payload."""
    if not dimensions_list:
        return 0.0, 0.0, 0.0, 0.0

    # Grab the first matched marketplace dimension set
    dim_data = dimensions_list[0]
    
    # Prefer package dimensions since that's what carriers use, fallback to item dims
    target = dim_data.get("package") or dim_data.get("item")
    if not target:
        return 0.0, 0.0, 0.0, 0.0

    l = parse_dimension_value(target.get("length"))
    w = parse_dimension_value(target.get("width"))
    h = parse_dimension_value(target.get("height"))
    wt = parse_weight_value(target.get("weight"))

    return l, w, h, wt

def sync_dimensions_batch(limit: int = 50) -> dict:
    """
    Real-Time Batch Ingestion:
    Fetches SKUs missing dimensions or details directly from Supabase.
    Iterates sequentially, fetches via Catalog SP-API, and upserts instantly.
    """
    stats = {"processed": 0, "updated": 0, "errors": []}
    
    # 1. Query Supabase for SKUs missing dimensions
    logger.info(f"Querying database for up to {limit} SKUs requiring dimension/details sync...")
    response = (
        supabase.table("sku_master")
        .select("sku, asin")
        .or_("length_cm.is.null,weight_kg.is.null,brand.is.null,category.is.null")
        .limit(limit)
        .execute()
    )
    
    skus_to_sync = response.data
    if not skus_to_sync:
        logger.info("[SUCCESS] Database is fully populated with dimensions and details. No missing data found.")
        return stats
        
    logger.info(f"Found {len(skus_to_sync)} SKUs. Beginning staggered SP-API requests...")
        
    # 2. Iterate and Update Real-Time
    for row in skus_to_sync:
        sku = row["sku"]
        asin = row.get("asin")
        
        if not asin:
            logger.warning(f"[SKIP] SKU {sku} has no ASIN mappings. Skipping...")
            stats["errors"].append(f"SKU {sku}: No ASIN")
            continue
            
        try:
            # 2a. SP-API Fetch
            api_res = sp_api_client.get_catalog_item(asin)
            payload = api_res.payload if hasattr(api_res, 'payload') else {}
            
            # 3. Safe JSON Parsing
            # Brand: inside attributes -> brand -> list[0] -> value
            brand = payload.get("attributes", {}).get("brand", [{"value": None}])[0].get("value")
            
            # Category: inside productTypes -> list[0] -> productType
            category = payload.get("productTypes", [{"productType": None}])[0].get("productType")
            
            # Dimensions: inside dimensions -> list[0] -> package or item
            dim_list = payload.get("dimensions", [{}])
            first_dim = dim_list[0] if dim_list else {}
            target_dim = first_dim.get("package") or first_dim.get("item") or {}
            
            l, w, h, wt = 0.0, 0.0, 0.0, 0.0
            if target_dim:
                l = parse_dimension_value(target_dim.get("length"))
                w = parse_dimension_value(target_dim.get("width"))
                h = parse_dimension_value(target_dim.get("height"))
                wt = parse_weight_value(target_dim.get("weight"))
            
            # Build update dict removing any None values
            update_data = {}
            if brand is not None: update_data["brand"] = brand
            if category is not None: update_data["category"] = category
            if l: update_data["length_cm"] = l
            if w: update_data["width_cm"] = w
            if h: update_data["height_cm"] = h
            if wt: update_data["weight_kg"] = wt

            if not update_data:
                logger.info(f"[WARN] Amazon returned no parseable data for ASIN {asin} (SKU: {sku})")
                stats["errors"].append(f"SKU {sku}: No parseable data")
            else:
                # 5. Database Update
                (
                    supabase.table("sku_master")
                    .update(update_data)
                    .eq("sku", sku)
                    .execute()
                )
                
                dim_str = f"{l}x{w}x{h}cm, {wt}kg" if l or wt else "No dims"
                logger.info(f"[SUCCESS] Updated ASIN {asin} (SKU: {sku}) | Brand: {brand} | Cat: {category} | Dims: {dim_str}")
                stats["updated"] += 1
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to update dimensions for SKU {sku}: {e}")
            stats["errors"].append(f"SKU {sku}: {str(e)}")
            
        stats["processed"] += 1
        
        # 3. Rate Limit Cooldown Wait
        time.sleep(0.5)
        
    logger.info(f"Batch sync completed. Updated {stats['updated']} entries.")
    return stats
