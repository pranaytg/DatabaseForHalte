export interface WarehouseSummary {
  warehouse_id: string;
  warehouse_name: string;
  fulfillment_channel: string;
  total_skus: number;
  total_quantity: number;
  total_inbound: number;
  total_reserved: number;
}

export interface InventoryItem {
  id: string;
  sku: string;
  warehouse_id: string;
  warehouse_name: string;
  fulfillment_channel: string;
  quantity: number;
  quantity_inbound: number;
  quantity_reserved: number;
  quantity_unfulfillable: number;
  last_synced_at: string;
  sku_master: {
    product_name: string;
    asin: string | null;
    is_active: boolean;
  };
  velocity30d?: number;
  dailyVelocity?: number;
  dos?: number;
  restockRec?: number;
}

export interface InventoryResponse {
  inventory: InventoryItem[];
  count: number;
}

export interface WarehouseSummaryResponse {
  warehouses: WarehouseSummary[];
}
