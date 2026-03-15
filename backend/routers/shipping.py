"""
Shipping router — shipping cost calculator API.
"""

from fastapi import APIRouter, HTTPException
import logging

from ..models import ShippingRequest, ShippingEstimateResponse
from ..services.shipping_calculator import estimate_shipping

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/shipping", tags=["Shipping"])


@router.post("/estimate", response_model=ShippingEstimateResponse)
async def calculate_shipping(request: ShippingRequest):
    """
    Calculate advanced shipping cost for easy_ship, BlueDart (Air/Surface), and Delhivery.
    Returns zone, billable weight, costs per carrier, and recommendation.
    """
    try:
        result = estimate_shipping(
            origin_pincode=request.origin_pincode,
            destination_pincode=request.destination_pincode,
            actual_weight_kg=request.actual_weight_kg,
            length_cm=request.length_cm,
            width_cm=request.width_cm,
            height_cm=request.height_cm,
            is_flyer=request.is_flyer,
            is_cod=request.is_cod,
            item_value=request.item_value
        )

        return ShippingEstimateResponse(
            zone=result.zone,
            fba=result.fba,
            bluedart_air=result.bluedart_air,
            bluedart_surface=result.bluedart_surface,
            delhivery=result.delhivery,
            recommended_carrier=result.recommended_carrier,
            recommended_cost=result.recommended_cost,
            metrics=result.metrics
        )
    except Exception as e:
        logger.error(f"Shipping estimate error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/estimate/sku/{sku}")
async def calculate_shipping_for_sku(
    sku: str,
    destination_pincode: str,
    origin_pincode: str = "160017",  # Default: Chandigarh (configurable)
    is_flyer: bool = False,
    is_cod: bool = False,
    item_value: float = 0.0,
):
    """
    Calculate shipping for a specific SKU — uses dimensions from sku_master.
    Falls back to default dimensions if not set.
    """
    try:
        from ..database import supabase

        response = (
            supabase.table("sku_master")
            .select("weight_kg, length_cm, width_cm, height_cm, cogs")
            .eq("sku", sku)
            .execute()
        )

        if not response.data:
            raise HTTPException(status_code=404, detail=f"SKU {sku} not found")

        product = response.data[0]
        weight = float(product.get("weight_kg") or 0.5)
        length = float(product.get("length_cm") or 20)
        width = float(product.get("width_cm") or 15)
        height = float(product.get("height_cm") or 10)
        
        # Use COGS roughly as item value if item_value not provided for COD
        if is_cod and item_value == 0:
            item_value = float(product.get("cogs") or 500)

        result = estimate_shipping(
            origin_pincode=origin_pincode,
            destination_pincode=destination_pincode,
            actual_weight_kg=weight,
            length_cm=length,
            width_cm=width,
            height_cm=height,
            is_flyer=is_flyer,
            is_cod=is_cod,
            item_value=item_value
        )

        return {
            "sku": sku,
            "dimensions_used": {
                "weight_kg": weight,
                "length_cm": length,
                "width_cm": width,
                "height_cm": height,
            },
            "estimate": ShippingEstimateResponse(
                zone=result.zone,
                fba=result.fba,
                bluedart_air=result.bluedart_air,
                bluedart_surface=result.bluedart_surface,
                delhivery=result.delhivery,
                recommended_carrier=result.recommended_carrier,
                recommended_cost=result.recommended_cost,
                metrics=result.metrics
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SKU shipping estimate error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
