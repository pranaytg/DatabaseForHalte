"""
Pydantic models — request/response schemas for the API.
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ── SKU Master ───────────────────────────────────────────────────────────────

class SKUBase(BaseModel):
    sku: str
    asin: Optional[str] = None
    fnsku: Optional[str] = None
    product_name: str
    category: Optional[str] = None
    brand: Optional[str] = None
    cogs: float = 0.0
    weight_kg: Optional[float] = None
    length_cm: Optional[float] = None
    width_cm: Optional[float] = None
    height_cm: Optional[float] = None
    channel: str = "amazon"
    is_active: bool = True


class COGSUpdate(BaseModel):
    cogs: float


# ── Warehouse Inventory ──────────────────────────────────────────────────────

class WarehouseInventoryItem(BaseModel):
    sku: str
    warehouse_id: str
    warehouse_name: Optional[str] = None
    fulfillment_channel: str = "FBA"
    quantity: int = 0
    quantity_inbound: int = 0
    quantity_reserved: int = 0
    quantity_unfulfillable: int = 0
    days_of_supply: Optional[int] = None
    last_synced_at: Optional[datetime] = None


# ── Orders ───────────────────────────────────────────────────────────────────

class OrderItem(BaseModel):
    sku: str
    asin: Optional[str] = None
    order_item_id: Optional[str] = None
    quantity: int = 1
    item_price: float = 0.0
    item_tax: float = 0.0
    shipping_price: float = 0.0
    shipping_tax: float = 0.0
    promotion_discount: float = 0.0
    referral_fee: float = 0.0
    fba_fee: float = 0.0
    commission: float = 0.0
    other_fees: float = 0.0
    unit_cogs: float = 0.0
    cogs_total: float = 0.0
    shipping_cost: float = 0.0
    total_fees: float = 0.0
    net_profit: float = 0.0
    profit_margin_pct: float = 0.0


class OrderResponse(BaseModel):
    id: str
    amazon_order_id: str
    purchase_date: datetime
    order_status: str
    fulfillment_channel: str
    order_total: float
    buyer_name: Optional[str] = None
    shipping_city: Optional[str] = None
    shipping_state: Optional[str] = None


# ── Dashboard summary ────────────────────────────────────────────────────────

class DashboardSummary(BaseModel):
    total_revenue: float
    total_orders: int
    total_net_profit: float
    avg_margin_pct: float
    fba_orders: int
    fbm_orders: int
    total_skus: int
    total_inventory_units: int


# ── Profitability ────────────────────────────────────────────────────────────

class SKUProfitability(BaseModel):
    sku: str
    asin: Optional[str] = None
    product_name: str
    current_unit_cogs: float
    units_sold: int
    total_revenue: float
    total_amazon_fees: float
    total_shipping_cost: float
    total_cogs: float
    total_net_profit: float
    net_margin_pct: float
    order_count: int


class OrderProfitability(BaseModel):
    order_id: str
    amazon_order_id: str
    purchase_date: datetime
    order_status: str
    fulfillment_channel: str
    order_total: float
    line_item_revenue: float
    total_fees: float
    total_shipping_cost: float
    total_cogs: float
    net_profit: float
    net_margin_pct: float


# ── Shipping calculator ─────────────────────────────────────────────────────

class ShippingRequest(BaseModel):
    origin_pincode: str
    destination_pincode: str
    actual_weight_kg: float
    length_cm: float
    width_cm: float
    height_cm: float
    is_flyer: bool = False
    is_cod: bool = False
    item_value: float = 0.0


class ShippingMetrics(BaseModel):
    amz_chargeable_kg: float
    delhivery_chargeable_kg: float
    bluedart_air_chargeable_kg: float
    bluedart_surface_chargeable_kg: float

class ShippingEstimateResponse(BaseModel):
    zone: str
    fba: float
    bluedart_air: float
    bluedart_surface: float
    delhivery: float
    recommended_carrier: str
    recommended_cost: float
    metrics: ShippingMetrics


# ── Sync responses ───────────────────────────────────────────────────────────

class SyncResult(BaseModel):
    status: str
    records_processed: int = 0
    records_created: int = 0
    records_updated: int = 0
    errors: List[str] = []
    duration_seconds: float = 0.0
