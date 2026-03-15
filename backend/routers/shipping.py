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
    Calculate shipping cost for FBA, BlueDart, and Delhivery.
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
        )

        return ShippingEstimateResponse(
            zone=result.zone,
            billable_weight_kg=result.billable_weight_kg,
            fba=result.fba,
            bluedart=result.bluedart,
            delhivery=result.delhivery,
            recommended_carrier=result.recommended_carrier,
            recommended_cost=result.recommended_cost,
        )
    except Exception as e:
        logger.error(f"Shipping estimate error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/estimate/sku/{sku}")
async def calculate_shipping_for_sku(
    sku: str,
    destination_pincode: str,
    origin_pincode: str = "160017",  # Default: Chandigarh (configurable)
):
    """
    Calculate shipping for a specific SKU — uses dimensions from sku_master.
    Falls back to default dimensions if not set.
    """
    try:
        from ..database import supabase

        response = (
            supabase.table("sku_master")
            .select("weight_kg, length_cm, width_cm, height_cm")
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

        result = estimate_shipping(
            origin_pincode=origin_pincode,
            destination_pincode=destination_pincode,
            actual_weight_kg=weight,
            length_cm=length,
            width_cm=width,
            height_cm=height,
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
                billable_weight_kg=result.billable_weight_kg,
                fba=result.fba,
                bluedart=result.bluedart,
                delhivery=result.delhivery,
                recommended_carrier=result.recommended_carrier,
                recommended_cost=result.recommended_cost,
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SKU shipping estimate error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
