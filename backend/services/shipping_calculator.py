"""
Shipping calculator — integrated from InventoryShipment/shipping_calculator.py.

Calculates shipping cost for Amazon FBA (Easy Ship), BlueDart, and Delhivery.
Rates are approximate 2024-25 India domestic rates.
Zone is determined from origin/destination pincodes.
Billable weight = max(actual weight, volumetric weight).
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


# ── Zone determination ────────────────────────────────────────────────────

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
    """Returns one of: Local, Zonal, Metro, National, Special"""
    if not destination or len(destination) < 3:
        return "National"
    if destination[:3] in SPECIAL_PREFIXES:
        return "Special"
    if origin[:3] == destination[:3]:
        return "Local"
    if origin[0] == destination[0]:
        return "Zonal"
    if origin[:3] in METRO_PREFIXES and destination[:3] in METRO_PREFIXES:
        return "Metro"
    nearby = _NEARBY_REGIONS.get(origin[0], {origin[0]})
    if destination[0] in nearby:
        return "Zonal"
    return "National"


# ── Weight calculations ──────────────────────────────────────────────────

def volumetric_weight(length_cm: float, width_cm: float, height_cm: float) -> float:
    return (length_cm * width_cm * height_cm) / 5000.0


def billable_weight(actual_kg: float, length_cm: float, width_cm: float, height_cm: float) -> float:
    return max(actual_kg, volumetric_weight(length_cm, width_cm, height_cm))


def _weight_slabs(weight_kg: float) -> int:
    return max(1, math.ceil(weight_kg / 0.5))


# ── Rate tables (₹) ─────────────────────────────────────────────────────

AMAZON_FBA_RATES = {
    "Local": (29, 10), "Zonal": (43, 14), "Metro": (43, 14),
    "National": (65, 18), "Special": (90, 30),
}
BLUEDART_RATES = {
    "Local": (38, 16), "Zonal": (58, 21), "Metro": (72, 24),
    "National": (88, 30), "Special": (125, 42),
}
DELHIVERY_RATES = {
    "Local": (32, 13), "Zonal": (50, 18), "Metro": (62, 20),
    "National": (78, 26), "Special": (112, 37),
}
FUEL_SURCHARGE = {"Amazon FBA": 0.00, "BlueDart": 0.18, "Delhivery": 0.15}


def _calc_cost(rates: dict, zone: str, weight_kg: float, fuel_pct: float) -> float:
    base, extra = rates.get(zone, rates["National"])
    slabs = _weight_slabs(weight_kg)
    raw = base + max(0, slabs - 1) * extra
    return round(raw * (1 + fuel_pct), 2)


# ── All-in-one estimate ─────────────────────────────────────────────────

@dataclass
class ShippingEstimate:
    zone: str
    billable_weight_kg: float
    fba: float
    bluedart: float
    delhivery: float
    recommended_carrier: str
    recommended_cost: float


def estimate_shipping(
    origin_pincode: str,
    destination_pincode: str,
    actual_weight_kg: float,
    length_cm: float,
    width_cm: float,
    height_cm: float,
) -> ShippingEstimate:
    """Calculate shipping cost for all three carriers and recommend the cheapest."""
    zone = determine_zone(origin_pincode, destination_pincode)
    bw = round(billable_weight(actual_weight_kg, length_cm, width_cm, height_cm), 3)

    costs = {
        "Amazon FBA": _calc_cost(AMAZON_FBA_RATES, zone, bw, FUEL_SURCHARGE["Amazon FBA"]),
        "BlueDart": _calc_cost(BLUEDART_RATES, zone, bw, FUEL_SURCHARGE["BlueDart"]),
        "Delhivery": _calc_cost(DELHIVERY_RATES, zone, bw, FUEL_SURCHARGE["Delhivery"]),
    }

    best = min(costs, key=costs.get)

    return ShippingEstimate(
        zone=zone,
        billable_weight_kg=bw,
        fba=costs["Amazon FBA"],
        bluedart=costs["BlueDart"],
        delhivery=costs["Delhivery"],
        recommended_carrier=best,
        recommended_cost=costs[best],
    )
