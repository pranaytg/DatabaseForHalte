export interface SkuProfitability {
  sku: string;
  product_name: string;
  channel: string;
  current_unit_cogs: number;
  total_units_sold: number;
  total_revenue: number;
  total_amazon_fees: number;
  total_shipping_cost: number;
  total_cogs: number;
  total_net_profit: number;
  avg_profit_margin_pct: number;
  last_order_date: string;
}

export interface SkuProfitabilityResponse {
  sku_profitability: SkuProfitability[];
  count: number;
}
