"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Edit2, Loader2 } from "lucide-react";
import { SkuProfitability } from "@/types/profitability";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { fetchApi } from "@/lib/api";

function getErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Failed to update COGS";
}

export function ProfitabilityTable({ data }: { data: SkuProfitability[] }) {
  const router = useRouter();

  // State for COGS editing dialog
  const [editingSku, setEditingSku] = useState<SkuProfitability | null>(null);
  const [newCogs, setNewCogs] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  // Search filter
  const [searchTerm, setSearchTerm] = useState("");

  const filteredData = data.filter((item) => {
    const term = searchTerm.toLowerCase();
    return (
      item.sku.toLowerCase().includes(term) ||
      (item.product_name || "").toLowerCase().includes(term)
    );
  });

  const handleEditClick = (skuData: SkuProfitability) => {
    setEditingSku(skuData);
    setNewCogs(skuData.current_unit_cogs.toString());
    setIsDialogOpen(true);
  };

  const handleSaveCogs = async () => {
    if (!editingSku) return;

    const cogsValue = parseFloat(newCogs);
    if (isNaN(cogsValue) || cogsValue < 0) {
      toast.error("Please enter a valid positive number for COGS.");
      return;
    }

    setIsSubmitting(true);

    try {
      await fetchApi<{ message: string }>(
        `dashboard/skus/${editingSku.sku}/cogs`,
        {
          method: "PUT",
          body: JSON.stringify({ cogs: cogsValue }),
        },
      );

      toast.success(`COGS updated for ${editingSku.sku}`);

      // Close dialog and refresh server data without a full page reload!
      setIsDialogOpen(false);
      setEditingSku(null);
      router.refresh();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Card className="col-span-full">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>SKU Profitability Leaderboard</CardTitle>
        <div className="w-1/3">
          <Input
            placeholder="Search SKU or Product..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </CardHeader>
      <CardContent>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[180px]">SKU</TableHead>
                <TableHead>Product Name</TableHead>
                <TableHead className="text-right">Current COGS</TableHead>
                <TableHead className="text-right">Units Sold</TableHead>
                <TableHead className="text-right">Total Revenue</TableHead>
                <TableHead className="text-right">Amazon Fees</TableHead>
                <TableHead className="text-right">Total Net Profit</TableHead>
                <TableHead className="text-right">Net Margin</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredData.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="h-24 text-center">
                    No results found.
                  </TableCell>
                </TableRow>
              ) : (
                filteredData.map((item) => (
                  <TableRow key={item.sku}>
                    <TableCell className="font-medium">
                      <div className="flex flex-col gap-1">
                        <span>{item.sku}</span>
                        <Badge
                          variant="outline"
                          className="w-fit text-[10px] leading-tight"
                        >
                          {item.channel}
                        </Badge>
                      </div>
                    </TableCell>
                    <TableCell
                      className="max-w-[200px] truncate"
                      title={item.product_name}
                    >
                      {item.product_name || "Unknown"}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <span className="font-semibold text-muted-foreground">
                          {formatCurrency(item.current_unit_cogs)}
                        </span>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6 text-muted-foreground hover:text-foreground"
                          onClick={() => handleEditClick(item)}
                        >
                          <Edit2 className="h-3 w-3" />
                          <span className="sr-only">Edit COGS</span>
                        </Button>
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      {item.total_units_sold}
                    </TableCell>
                    <TableCell className="text-right">
                      {formatCurrency(item.total_revenue)}
                    </TableCell>
                    <TableCell className="text-right text-red-500/80">
                      -{formatCurrency(item.total_amazon_fees)}
                    </TableCell>
                    <TableCell
                      className={`text-right font-bold ${item.total_net_profit > 0 ? "text-green-600" : "text-red-600"}`}
                    >
                      {formatCurrency(item.total_net_profit)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Badge
                        variant={
                          item.avg_profit_margin_pct >= 20
                            ? "default"
                            : item.avg_profit_margin_pct > 0
                              ? "secondary"
                              : "destructive"
                        }
                      >
                        {formatPercent(item.avg_profit_margin_pct)}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </CardContent>

      {/* COGS Edit Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Edit Cost of Goods Sold (COGS)</DialogTitle>
            <DialogDescription>
              Update the COGS for <strong>{editingSku?.sku}</strong>. This will
              only affect <em>future</em> orders synced from Amazon.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-4 items-center gap-4">
              <label htmlFor="cogs" className="text-right text-sm font-medium">
                Unit COGS (₹)
              </label>
              <Input
                id="cogs"
                type="number"
                step="0.01"
                min="0"
                value={newCogs}
                onChange={(e) => setNewCogs(e.target.value)}
                className="col-span-3"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsDialogOpen(false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button onClick={handleSaveCogs} disabled={isSubmitting}>
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                "Save changes"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
