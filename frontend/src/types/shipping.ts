export interface ShippingRequest {
  origin_pincode: string;
  destination_pincode: string;
  actual_weight_kg: number;
  length_cm: number;
  width_cm: number;
  height_cm: number;
}

export interface ShippingEstimateResponse {
  zone: string;
  billable_weight_kg: number;
  fba: number;
  bluedart: number;
  delhivery: number;
  recommended_carrier: string;
  recommended_cost: number;
}

export interface SkuShippingResponse {
  sku: string;
  dimensions_used: {
    weight_kg: number;
    length_cm: number;
    width_cm: number;
    height_cm: number;
  };
  estimate: ShippingEstimateResponse;
}
