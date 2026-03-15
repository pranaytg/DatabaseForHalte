import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  RevenueProfitAreaChart,
  type RevenueProfitPoint,
} from "@/components/dashboard/RevenueProfitAreaChart";
import KPICards from "@/components/dashboard/KPICards";
import { formatCurrency } from "@/lib/utils";
import { getSupabaseServerClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

type OrderRow = {
  id: string;
  amazon_order_id: string;
  purchase_date: string;
  order_total: number | string | null;
  ad_spend?: number | string | null;
  shipping_cost?: number | string | null;
};

type OrderItemRow = {
  order_id: string;
  net_profit: number | string | null;
  cogs_total: number | string | null;
  total_fees: number | string | null;
};

type KpiSnapshot = {
  totalRevenue: number;
  trueNetProfit: number;
  blendedProfitMarginPct: number;
  totalOrders: number;
};

function asNumber(value: number | string | null | undefined) {
  return Number(value ?? 0);
}

function getDateLabel(date: Date) {
  return date.toLocaleDateString("en-IN", { month: "short", day: "numeric" });
}

function createLast30DaySeries(
  orders: OrderRow[],
  orderItems: OrderItemRow[],
): { kpis: KpiSnapshot; chartData: RevenueProfitPoint[] } {
  const today = new Date();
  const dayKeys: string[] = [];
  const dayLabelByKey = new Map<string, string>();

  for (let i = 29; i >= 0; i -= 1) {
    const date = new Date(today);
    date.setHours(0, 0, 0, 0);
    date.setDate(today.getDate() - i);

    const key = date.toISOString().slice(0, 10);
    dayKeys.push(key);
    dayLabelByKey.set(key, getDateLabel(date));
  }

  const revenueByDay = new Map<string, number>(dayKeys.map((k) => [k, 0]));
  const netByDay = new Map<string, number>(dayKeys.map((k) => [k, 0]));
  const orderDayById = new Map<string, string>();

  let totalRevenue = 0;

  for (const order of orders) {
    const dayKey = new Date(order.purchase_date).toISOString().slice(0, 10);
    if (!revenueByDay.has(dayKey)) continue;

    const orderTotal = asNumber(order.order_total);
    revenueByDay.set(dayKey, (revenueByDay.get(dayKey) ?? 0) + orderTotal);
    totalRevenue += orderTotal;
    orderDayById.set(order.id, dayKey);
  }

  let totalNetProfit = 0;
  let totalCogs = 0;
  let totalFees = 0;

  for (const item of orderItems) {
    const dayKey = orderDayById.get(item.order_id);
    if (!dayKey) continue;

    const net = asNumber(item.net_profit);
    const cogs = asNumber(item.cogs_total);
    const fees = asNumber(item.total_fees);

    netByDay.set(dayKey, (netByDay.get(dayKey) ?? 0) + net);

    totalNetProfit += net;
    totalCogs += cogs;
    totalFees += fees;
  }

  const fallbackTrueNetProfit = totalRevenue - totalCogs - totalFees;
  const trueNetProfit =
    totalNetProfit !== 0 ? totalNetProfit : fallbackTrueNetProfit;

  const blendedProfitMarginPct =
    totalRevenue > 0 ? (trueNetProfit / totalRevenue) * 100 : 0;

  const chartData: RevenueProfitPoint[] = dayKeys.map((dayKey) => ({
    day: dayLabelByKey.get(dayKey) ?? dayKey,
    revenue: revenueByDay.get(dayKey) ?? 0,
    netProfit: netByDay.get(dayKey) ?? 0,
  }));

  return {
    kpis: {
      totalRevenue,
      trueNetProfit,
      blendedProfitMarginPct,
      totalOrders: orders.length,
    },
    chartData,
  };
}

async function getDashboardData() {
  const supabase = await getSupabaseServerClient();

  const startDate = new Date();
  startDate.setDate(startDate.getDate() - 30);

  const { data: orders, error: ordersError } = await supabase
    .from("orders")
    .select("id,amazon_order_id,purchase_date,order_total")
    .gte("purchase_date", startDate.toISOString())
    .order("purchase_date", { ascending: true });

  if (ordersError) {
    throw new Error(`Failed to fetch orders: ${ordersError.message}`);
  }

  const typedOrders = (orders ?? []) as OrderRow[];
  const orderIds = typedOrders.map((order) => order.id);

  const typedOrderItems: OrderItemRow[] = [];

  if (orderIds.length > 0) {
    const chunkSize = 100;
    for (let i = 0; i < orderIds.length; i += chunkSize) {
      const chunk = orderIds.slice(i, i + chunkSize);
      const { data: orderItems, error: orderItemsError } = await supabase
        .from("order_items")
        .select("order_id,net_profit,cogs_total,total_fees")
        .in("order_id", chunk);

      if (orderItemsError) {
        throw new Error(
          `Failed to fetch order items: ${orderItemsError.message}`,
        );
      }

      if (orderItems) {
        typedOrderItems.push(...(orderItems as OrderItemRow[]));
      }
    }
  }

  // Fetch the new sellerboard styled API route payload
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
  let sellerBoardKpis = null;
  try {
    const res = await fetch(`${apiUrl}/dashboard/summary?days=60`, { cache: 'no-store' });
    if (res.ok) {
      sellerBoardKpis = await res.json();
    }
  } catch (error) {
    console.error("Could not fetch SellerBoard KPIs:", error);
  }

  return { ...createLast30DaySeries(typedOrders, typedOrderItems), sellerBoardKpis };
}

export default async function DashboardPage() {
  const { kpis, chartData, sellerBoardKpis } = await getDashboardData();

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight md:text-3xl text-slate-800">
          Executive Dashboard
        </h1>
        <p className="text-sm text-muted-foreground md:text-base">
          SellerBoard Style Overview
        </p>
      </div>

      {sellerBoardKpis ? (
        <KPICards data={sellerBoardKpis} />
      ) : (
        <div className="text-red-500">FastAPI backend is unavailable. Cannot load SellerBoard KPI tiles.</div>
      )}

      <div className="grid gap-6 mt-6">
        <RevenueProfitAreaChart data={chartData} />
      </div>
    </div>
  );
}
