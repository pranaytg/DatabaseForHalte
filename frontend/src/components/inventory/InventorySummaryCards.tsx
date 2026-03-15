import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { WarehouseSummary } from "@/types/inventory";
import { Package, Truck, Box } from "lucide-react";

export function InventorySummaryCards({ data }: { data: WarehouseSummary[] }) {
  // Aggregate totals
  const totalFba = data
    .filter((w) => w.fulfillment_channel === "FBA")
    .reduce((sum, w) => sum + (w.total_quantity || 0), 0);
    
  const totalFbm = data
    .filter((w) => w.fulfillment_channel === "FBM")
    .reduce((sum, w) => sum + (w.total_quantity || 0), 0);

  const totalInbound = data.reduce((sum, w) => sum + (w.total_inbound || 0), 0);

  return (
    <div className="grid gap-4 md:grid-cols-3">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">FBA Inventory</CardTitle>
          <Box className="h-4 w-4 text-blue-500" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{totalFba.toLocaleString()}</div>
          <p className="text-xs text-muted-foreground">Units at Amazon Fulfillment Centers</p>
        </CardContent>
      </Card>
      
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Local Inventory (FBM)</CardTitle>
          <Package className="h-4 w-4 text-orange-500" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{totalFbm.toLocaleString()}</div>
          <p className="text-xs text-muted-foreground">Units in self-managed warehouses</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Total Inbound</CardTitle>
          <Truck className="h-4 w-4 text-green-500" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{totalInbound.toLocaleString()}</div>
          <p className="text-xs text-muted-foreground">Units currently shipping to FBA</p>
        </CardContent>
      </Card>
    </div>
  );
}
