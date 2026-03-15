import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { OrderProfitability } from "@/types/dashboard";
import { formatCurrency } from "@/lib/utils";

export function RecentOrdersTable({ data }: { data: OrderProfitability[] }) {
  // Take only the 10 most recent orders
  const recentOrders = data.slice(0, 10);

  return (
    <Card className="col-span-full">
      <CardHeader>
        <CardTitle>Recent Orders</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Order ID</TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Channel</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Revenue</TableHead>
              <TableHead className="text-right">Net Profit</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {recentOrders.map((order) => (
              <TableRow key={order.amazon_order_id}>
                <TableCell className="font-medium text-xs">
                  {order.amazon_order_id}
                </TableCell>
                <TableCell className="text-muted-foreground text-sm">
                  {new Date(order.purchase_date).toLocaleDateString()}
                </TableCell>
                <TableCell>
                  <Badge variant={order.fulfillment_channel === "FBA" ? "default" : "secondary"}>
                    {order.fulfillment_channel}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Badge variant="outline">{order.order_status}</Badge>
                </TableCell>
                <TableCell className="text-right">
                  {formatCurrency(order.line_item_revenue)}
                </TableCell>
                <TableCell className={`text-right font-medium ${order.net_profit > 0 ? "text-green-600" : "text-red-600"}`}>
                  {formatCurrency(order.net_profit)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
