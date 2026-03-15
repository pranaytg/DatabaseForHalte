import { Suspense } from "react";
import { InventorySummaryCards } from "@/components/inventory/InventorySummaryCards";
import { InventoryTable } from "@/components/inventory/InventoryTable";
import { getSupabaseServerClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

function InventorySkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="grid gap-4 md:grid-cols-3">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-28 rounded-xl bg-muted" />
        ))}
      </div>
      <div className="h-[500px] rounded-xl bg-muted" />
    </div>
  );
}

async function InventoryContent() {
  const supabase = await getSupabaseServerClient();

  // 1. Fetch warehouse summaries
  const { data: warehouseData } = await supabase
    .from("warehouse_inventory")
    .select("warehouse_id, warehouse_name, fulfillment_channel, quantity, quantity_inbound, quantity_reserved, sku");

  const summaryMap: Record<string, any> = {};
  warehouseData?.forEach(w => {
    const key = `${w.warehouse_id}-${w.fulfillment_channel}`;
    if (!summaryMap[key]) {
      summaryMap[key] = {
        warehouse_id: w.warehouse_id,
        warehouse_name: w.warehouse_name,
        fulfillment_channel: w.fulfillment_channel,
        total_skus: 0,
        total_quantity: 0,
        total_inbound: 0,
        total_reserved: 0
      };
    }
    summaryMap[key].total_skus += 1;
    summaryMap[key].total_quantity += w.quantity || 0;
    summaryMap[key].total_inbound += w.quantity_inbound || 0;
    summaryMap[key].total_reserved += w.quantity_reserved || 0;
  });
  
  const summaryData = Object.values(summaryMap);

  // 2. Fetch inventory items with SKU details
  const { data: inventoryData } = await supabase
    .from("warehouse_inventory")
    .select(`
      id,
      sku,
      warehouse_id,
      warehouse_name,
      fulfillment_channel,
      quantity,
      quantity_inbound,
      quantity_reserved,
      quantity_unfulfillable,
      last_synced_at,
      sku_master!inner(
        product_name,
        asin,
        is_active
      )
    `)
    .limit(1000);

  // 3. Fetch past 30 days orders for forecasting
  const thirtyDaysAgo = new Date();
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
  
  const { data: salesData } = await supabase
    .from("order_items")
    .select(`
      sku,
      quantity,
      orders!inner(purchase_date)
    `)
    .gte("orders.purchase_date", thirtyDaysAgo.toISOString());

  // Aggregate sales by SKU
  const salesBySku: Record<string, number> = {};
  if (salesData) {
    salesData.forEach((item: any) => {
      salesBySku[item.sku] = (salesBySku[item.sku] || 0) + (item.quantity || 0);
    });
  }

  // Merge forecasting into inventoryData
  const enrichedInventory = (inventoryData || []).map((item) => {
    const velocity30d = salesBySku[item.sku] || 0;
    const dailyVelocity = velocity30d / 30;
    
    const available = item.quantity || 0;
    const inbound = item.quantity_inbound || 0;
    const totalAvailable = available + inbound;
    
    let dos = 999;
    if (dailyVelocity > 0) {
      dos = totalAvailable / dailyVelocity;
    }
    dos = Math.min(dos, 999);
    
    let restockRec = Math.ceil(45 * dailyVelocity - totalAvailable);
    if (restockRec < 0) restockRec = 0;
    
    return {
      ...item,
      velocity30d,
      dailyVelocity,
      dos,
      restockRec
    };
  });

  return (
    <div className="space-y-6">
      <InventorySummaryCards data={summaryData as any} />
      <InventoryTable data={enrichedInventory as any} />
    </div>
  );
}

export default function InventoryPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Inventory Manager</h2>
        <p className="text-muted-foreground">
          Track FBA and local stock levels across all fulfillment networks.
        </p>
      </div>

      <Suspense fallback={<InventorySkeleton />}>
        <InventoryContent />
      </Suspense>
    </div>
  );
}
