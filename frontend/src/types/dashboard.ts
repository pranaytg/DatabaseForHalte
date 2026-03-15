export interface DashboardSummary {
  total_revenue: number;
  total_orders: number;
  total_net_profit: number;
  avg_margin_pct: number;
  fba_orders: number;
  fbm_orders: number;
  total_skus: number;
  total_inventory_units: number;
}

export interface OrderProfitability {
  amazon_order_id: string;
  purchase_date: string;
  order_status: string;
  fulfillment_channel: string;
  line_item_revenue: number;
  total_fees: number;
  shipping_cost: number;
  total_cogs: number;
  net_profit: number;
  profit_margin_pct: number;
}

export interface OrderProfitabilityResponse {
  order_profitability: OrderProfitability[];
  count: number;
}
