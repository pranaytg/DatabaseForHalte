"""
Advanced Logistics & Shipping Calculator

Implements industry-standard logic for Delhivery, Amazon India (Easy Ship/FBA), and Blue Dart.
Uses strictly accurate volumetric divisior formulas, flyer exceptions, step rates, and step ceilings.
"""

from __future__ import annotations
import math
from dataclasses import dataclass

# ── Metro / Special pincode prefixes ──────────────────────────────────────

METRO_PREFIXES = {
    "110", "120", "121", "122", "201",  # Delhi / NCR
    "400", "401",                        # Mumbai
    "411",                               # Pune
    "560",                               # Bangalore
    "600",                               # Chennai
    "500",                               # Hyderabad
    "700",                               # Kolkata
    "380",                               # Ahmedabad
}

SPECIAL_PREFIXES = {
    "790", "791", "792", "793", "794", "795", "796", "797",  # Northeast
    "180", "181", "182", "184", "185", "186",                 # J&K / Ladakh
    "190", "191", "192", "193", "194",
    "744",                                                    # Andaman & Nicobar
    "682",                                                    # Lakshadweep
}

_NEARBY_REGIONS: dict[str, set[str]] = {
    "1": {"1", "2"},
    "2": {"1", "2", "3"},
    "3": {"2", "3", "4"},
    "4": {"3", "4", "5"},
    "5": {"4", "5", "6"},
    "6": {"5", "6"},
    "7": {"7", "8"},
    "8": {"7", "8"},
}


def determine_zone(origin: str, destination: str) -> str:
    """Returns one of: Local, Regional, National, Special (Maps Metro to National for generic)."""
    if not destination or len(destination) < 3:
        return "National"
    if destination[:3] in SPECIAL_PREFIXES:
        return "Special"
    if origin[:3] == destination[:3]:
        return "Local"
    if origin[0] == destination[0]:
        return "Regional"
    nearby = _NEARBY_REGIONS.get(origin[0], {origin[0]})
    if destination[0] in nearby:
        return "Regional"
    return "National"


# ── Core Calculators ────────────────────────────────────────────────────────

def get_chargeable_weight(
    actual_weight: float,
    length: float,
    width: float,
    height: float,
    divisor: float
) -> float:
    """The industry standard volumetric equation."""
    volumetric_weight = (length * width * height) / divisor
    return max(actual_weight, volumetric_weight)

def calculate_step_slabs(chargeable_weight: float, base_slab: float, step_slab: float) -> int:
    """Calculate the number of additional step slabs above the base limit."""
    if chargeable_weight <= base_slab:
        return 0
    return math.ceil((chargeable_weight - base_slab) / step_slab)

def apply_gst(amount: float) -> float:
    """Apply standard 18% GST."""
    return round(amount * 1.18, 2)


# ── 1. Delhivery Calculation ────────────────────────────────────────────────

DELHIVERY_RATES = {
    "Local": {"base_rate": 32, "step_rate": 13},
    "Regional": {"base_rate": 50, "step_rate": 18},
    "National": {"base_rate": 78, "step_rate": 26},
    "Special": {"base_rate": 112, "step_rate": 37},
}

def calculate_delhivery(
    zone: str, 
    actual_weight: float, 
    L: float, W: float, H: float, 
    is_flyer: bool = False,
    is_cod: bool = False,
    item_value: float = 0
) -> (float, float):
    
    # Flyer exception logic
    if is_flyer and actual_weight < 1.0:
        chargeable_wt = actual_weight
    else:
        chargeable_wt = get_chargeable_weight(actual_weight, L, W, H, divisor=5000)
    
    rates = DELHIVERY_RATES.get(zone, DELHIVERY_RATES["National"])
    step_multiplier = calculate_step_slabs(chargeable_wt, base_slab=0.5, step_slab=0.5)
    
    total_freight = rates["base_rate"] + (rates["step_rate"] * step_multiplier)
    
    # COD Surcharge (Standard structure: Rs 50 or 2%, whichever higher)
    cod_fee = max(50.0, item_value * 0.02) if is_cod else 0.0
    
    final_cost = apply_gst(total_freight + cod_fee)
    return final_cost, chargeable_wt


# ── 2. Amazon Easy Ship Calculation ─────────────────────────────────────────

AMAZON_RATES = {
    "Local": {"base_rate": 43, "step_rate": 15},
    "Regional": {"base_rate": 54, "step_rate": 21},
    "National": {"base_rate": 74, "step_rate": 26},
    "Special": {"base_rate": 90, "step_rate": 30},
}

def calculate_amazon_easy_ship(
    zone: str, actual_weight: float, L: float, W: float, H: float
) -> (float, float):
    
    chargeable_wt = get_chargeable_weight(actual_weight, L, W, H, divisor=5000)
    rates = AMAZON_RATES.get(zone, AMAZON_RATES["National"])
    step_multiplier = calculate_step_slabs(chargeable_wt, base_slab=0.5, step_slab=0.5)
    
    total_freight = rates["base_rate"] + (rates["step_rate"] * step_multiplier)
    final_cost = apply_gst(total_freight)
    return final_cost, chargeable_wt


# ── 3. Blue Dart Calculation ────────────────────────────────────────────────

BLUEDART_RATES_AIR = {
    "Local": {"base_rate": 45, "step_rate": 25},
    "Regional": {"base_rate": 65, "step_rate": 30},
    "National": {"base_rate": 90, "step_rate": 45},
    "Special": {"base_rate": 130, "step_rate": 60},
}
BLUEDART_RATES_SURFACE = {
    "Local": {"base_rate": 30, "step_rate": 10},
    "Regional": {"base_rate": 45, "step_rate": 15},
    "National": {"base_rate": 65, "step_rate": 20},
    "Special": {"base_rate": 95, "step_rate": 30},
}

def calculate_blue_dart(
    zone: str, 
    actual_weight: float, 
    L: float, W: float, H: float, 
    surface_mode: bool = False,
    is_cod: bool = False,
    item_value: float = 0
) -> (float, float):
    
    divisor = 3000 if surface_mode else 5000
    chargeable_wt = get_chargeable_weight(actual_weight, L, W, H, divisor=divisor)
    
    rates = BLUEDART_RATES_SURFACE.get(zone) if surface_mode else BLUEDART_RATES_AIR.get(zone)
    if not rates:
        rates = BLUEDART_RATES_SURFACE["National"] if surface_mode else BLUEDART_RATES_AIR["National"]
        
    step_multiplier = calculate_step_slabs(chargeable_wt, base_slab=0.5, step_slab=0.5)
    
    total_freight = rates["base_rate"] + (rates["step_rate"] * step_multiplier)
    cod_fee = max(50.0, item_value * 0.02) if is_cod else 0.0
    
    final_cost = apply_gst(total_freight + cod_fee)
    return final_cost, chargeable_wt


# ── Main Entrypoint Estimate ────────────────────────────────────────────────

@dataclass
class DeliveryDetails:
    cost: float
    chargeable_weight: float
    breakdown_notes: str

@dataclass
class ShippingEstimate:
    zone: str
    fba: float  # we use Easy Ship logic below for FBA slot
    bluedart_air: float
    bluedart_surface: float
    delhivery: float
    recommended_carrier: str
    recommended_cost: float
    metrics: dict  # additional metadata


def estimate_shipping(
    origin_pincode: str,
    destination_pincode: str,
    actual_weight_kg: float,
    length_cm: float,
    width_cm: float,
    height_cm: float,
    is_flyer: bool = False,
    is_cod: bool = False,
    item_value: float = 0.0
) -> ShippingEstimate:
    """
    Dynamic and accurate logistics algorithm processing.
    """
    zone = determine_zone(origin_pincode, destination_pincode)

    delhivery_cost, bw_del = calculate_delhivery(
        zone, actual_weight_kg, length_cm, width_cm, height_cm, is_flyer, is_cod, item_value
    )
    
    amazon_cost, bw_amz = calculate_amazon_easy_ship(
        zone, actual_weight_kg, length_cm, width_cm, height_cm
    )
    
    bd_air_cost, bw_bd_air = calculate_blue_dart(
        zone, actual_weight_kg, length_cm, width_cm, height_cm, surface_mode=False, is_cod=is_cod, item_value=item_value
    )
    
    bd_surf_cost, bw_bd_surf = calculate_blue_dart(
        zone, actual_weight_kg, length_cm, width_cm, height_cm, surface_mode=True, is_cod=is_cod, item_value=item_value
    )

    costs = {
        "Amazon EasyShip": amazon_cost,
        "Delhivery": delhivery_cost,
        "BlueDart Air": bd_air_cost,
        "BlueDart Surface": bd_surf_cost,
    }

    best_carrier = min(costs, key=costs.get)

    return ShippingEstimate(
        zone=zone,
        fba=amazon_cost, 
        bluedart_air=bd_air_cost,
        bluedart_surface=bd_surf_cost,
        delhivery=delhivery_cost,
        recommended_carrier=best_carrier,
        recommended_cost=costs[best_carrier],
        metrics={
            "amz_chargeable_kg": bw_amz,
            "delhivery_chargeable_kg": bw_del,
            "bluedart_air_chargeable_kg": bw_bd_air,
            "bluedart_surface_chargeable_kg": bw_bd_surf,
        }
    )
