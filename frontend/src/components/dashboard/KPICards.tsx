"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { DollarSign, ShoppingCart, TrendingUp, Activity } from "lucide-react";
import { DashboardSummary } from "@/types/dashboard";

type MetricTile = {
  gross_sales: number;
  units_sold: number;
  ad_spend: number;
  estimated_shipping: number;
  net_profit: number;
  margin_pct: number;
};

type SellerBoardDashboardSummary = {
  today: MetricTile;
  yesterday: MetricTile;
  mtd: MetricTile;
  last_month: MetricTile;
};

function Tile({ title, data }: { title: string; data: MetricTile }) {
  const isPositive = data.net_profit >= 0;

  return (
    <Card className="shadow-sm border border-slate-200">
      <CardHeader className="bg-slate-50 border-b border-slate-100 py-3">
        <CardTitle className="text-sm font-semibold text-slate-700">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 space-y-4">
        {/* Top line metrics */}
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div>
            <p className="text-slate-500 font-medium">Gross</p>
            <p className="font-semibold text-slate-900">{formatCurrency(data.gross_sales)}</p>
          </div>
          <div>
            <p className="text-slate-500 font-medium">Units</p>
            <p className="font-semibold text-slate-900">{data.units_sold}</p>
          </div>
        </div>

        {/* Expense metrics */}
        <div className="grid grid-cols-2 gap-2 text-xs border-t border-slate-100 pt-3">
          <div>
            <p className="text-slate-500">Ad Spend</p>
            <p className="text-red-500 font-medium">{formatCurrency(data.ad_spend)}</p>
          </div>
          <div>
            <p className="text-slate-500">Est. Ship</p>
            <p className="text-red-500 font-medium">{formatCurrency(data.estimated_shipping)}</p>
          </div>
        </div>

        {/* Bottom line net profit */}
        <div className="bg-slate-50 rounded-md p-3 mt-4 flex justify-between items-center">
          <p className="font-semibold text-slate-700">Net Profit</p>
          <div className="text-right">
            <p className={`font-bold ${isPositive ? 'text-emerald-600' : 'text-red-600'}`}>
              {formatCurrency(data.net_profit)}
            </p>
            <p className={`text-xs font-semibold ${isPositive ? 'text-emerald-600' : 'text-red-600'}`}>
              {data.margin_pct.toFixed(2)}% margin
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}


export default function KPICards({ data }: { data: any }) {
  if (data?.today) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Tile title="Today" data={data.today} />
        <Tile title="Yesterday" data={data.yesterday} />
        <Tile title="Month to Date" data={data.mtd} />
        <Tile title="Last Month" data={data.last_month} />
      </div>
    );
  }

  // Fallback to legacy
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Total Gross Revenue</CardTitle>
          <DollarSign className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{formatCurrency(data.total_revenue)}</div>
          <p className="text-xs text-muted-foreground">Over the last 30 days</p>
        </CardContent>
      </Card>
      
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Total Net Profit</CardTitle>
          <TrendingUp className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold text-green-600">{formatCurrency(data.total_net_profit)}</div>
          <p className="text-xs text-muted-foreground">After all COGS and fees</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Avg Profit Margin</CardTitle>
          <Activity className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{formatPercent(data.avg_margin_pct)}</div>
          <p className="text-xs text-muted-foreground">Average margin per order</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Total Orders</CardTitle>
          <ShoppingCart className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{data.total_orders}</div>
          <p className="text-xs text-muted-foreground">
            {data.fba_orders} FBA / {data.fbm_orders} FBM
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
