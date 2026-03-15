"use client";

import { useState, useMemo } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowUpDown, AlertTriangle } from "lucide-react";
import { InventoryItem } from "@/types/inventory";

const LOW_STOCK_THRESHOLD = 20;

export function InventoryTable({ data }: { data: InventoryItem[] }) {
  const [searchTerm, setSearchTerm] = useState("");
  const [sortConfig, setSortConfig] = useState<{
    key: keyof InventoryItem;
    direction: "asc" | "desc";
  } | null>(null);

  // Filter and Sort Logic
  const filteredAndSortedData = useMemo(() => {
    // 1. Filter
    const processed = data.filter((item) => {
      const searchStr = searchTerm.toLowerCase();
      return (
        item.sku.toLowerCase().includes(searchStr) ||
        (item.sku_master?.product_name || "").toLowerCase().includes(searchStr)
      );
    });

    // 2. Sort
    if (sortConfig !== null) {
      processed.sort((a, b) => {
        let aValue = a[sortConfig.key];
        let bValue = b[sortConfig.key];

        if (aValue === undefined) aValue = "";
        if (bValue === undefined) bValue = "";

        if (aValue < bValue) {
          return sortConfig.direction === "asc" ? -1 : 1;
        }
        if (aValue > bValue) {
          return sortConfig.direction === "asc" ? 1 : -1;
        }
        return 0;
      });
    }

    return processed;
  }, [data, searchTerm, sortConfig]);

  const requestSort = (key: keyof InventoryItem) => {
    let direction: "asc" | "desc" = "asc";
    if (
      sortConfig &&
      sortConfig.key === key &&
      sortConfig.direction === "asc"
    ) {
      direction = "desc";
    }
    setSortConfig({ key, direction });
  };

  return (
    <Card className="col-span-full">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Inventory Tracker</CardTitle>
        <div className="w-1/3">
          <Input
            placeholder="Search by SKU or Product Name..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="max-w-sm"
          />
        </div>
      </CardHeader>
      <CardContent>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[150px]">SKU</TableHead>
                <TableHead>Product Name</TableHead>
                <TableHead>Channel</TableHead>
                <TableHead
                  className="text-right cursor-pointer hover:bg-muted/50"
                  onClick={() => requestSort("quantity")}
                >
                  <div className="flex items-center justify-end gap-1">
                    Available
                    <ArrowUpDown className="h-4 w-4" />
                  </div>
                </TableHead>
                <TableHead
                  className="text-right cursor-pointer hover:bg-muted/50"
                  onClick={() => requestSort("quantity_inbound")}
                >
                  <div className="flex items-center justify-end gap-1">
                    Inbound
                    <ArrowUpDown className="h-4 w-4" />
                  </div>
                </TableHead>
                <TableHead className="text-right">30d Velocity</TableHead>
                <TableHead className="text-right">DOS</TableHead>
                <TableHead className="text-right">Restock Rec</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredAndSortedData.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="h-24 text-center">
                    No results found.
                  </TableCell>
                </TableRow>
              ) : (
                filteredAndSortedData.map((item) => {
                  const isLowStock = item.quantity === 0 || item.quantity < LOW_STOCK_THRESHOLD;

                  let dosBadgeColor = "bg-green-500";
                  if (item.dos !== undefined) {
                    if (item.dos < 15) {
                      dosBadgeColor = "bg-red-500 text-white";
                    } else if (item.dos <= 30) {
                      dosBadgeColor = "bg-yellow-500 text-white";
                    }
                  }

                  return (
                    <TableRow
                      key={item.id}
                      className={isLowStock ? "bg-red-50/50 hover:bg-red-50" : ""}
                    >
                      <TableCell className="font-medium">
                        {item.sku}
                        {item.quantity === 0 && (
                          <AlertTriangle className="inline-block ml-2 h-4 w-4 text-red-500" />
                        )}
                      </TableCell>
                      <TableCell className="max-w-[250px] truncate" title={item.sku_master?.product_name}>
                        {item.sku_master?.product_name || "Unknown"}
                      </TableCell>
                      <TableCell>
                        <Badge variant={item.fulfillment_channel === "FBA" ? "default" : "secondary"}>
                          {item.fulfillment_channel}
                        </Badge>
                      </TableCell>
                      <TableCell className={`text-right font-medium ${isLowStock ? "text-red-600" : ""}`}>
                        {(item.quantity || 0).toLocaleString()}
                      </TableCell>
                      <TableCell className="text-right text-muted-foreground">
                        {(item.quantity_inbound || 0).toLocaleString()}
                      </TableCell>
                      <TableCell className="text-right text-muted-foreground">
                        {item.velocity30d} units / {item.dailyVelocity?.toFixed(1)} daily
                      </TableCell>
                      <TableCell className="text-right">
                        <Badge className={`${dosBadgeColor} hover:${dosBadgeColor} border-none`}>
                          {item.dos === 999 ? "999+" : item.dos?.toFixed(0)} days
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right font-medium">
                        {item.restockRec?.toLocaleString()}
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
