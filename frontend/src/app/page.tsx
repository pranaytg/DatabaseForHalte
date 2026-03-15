import { Suspense } from "react";
import KPICards from "@/components/dashboard/KPICards";
import { PerformanceChart } from "@/components/dashboard/PerformanceChart";
import { RecentOrdersTable } from "@/components/dashboard/RecentOrdersTable";
import { fetchApi } from "@/lib/api";
import {
  DashboardSummary,
  OrderProfitabilityResponse,
} from "@/types/dashboard";

export const dynamic = "force-dynamic";

function DashboardSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-28 rounded-xl bg-muted" />
        ))}
      </div>
      <div className="h-[400px] rounded-xl bg-muted" />
      <div className="h-[300px] rounded-xl bg-muted" />
    </div>
  );
}

async function DashboardContent() {
  // Fetch data in parallel with no caching to ensure fresh data
  const [summary, ordersData] = await Promise.all([
    fetchApi<DashboardSummary>("dashboard/summary?days=30", {
      cache: "no-store",
    }),
    fetchApi<OrderProfitabilityResponse>(
      "profitability/orders?days=30&limit=100",
      { cache: "no-store" },
    ),
  ]);

  return (
    <div className="space-y-6">
      <KPICards data={summary} />
      <PerformanceChart data={ordersData.order_profitability} />
      <RecentOrdersTable data={ordersData.order_profitability} />
    </div>
  );
}

export default function Home() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">
          Dashboard Overview
        </h2>
        <p className="text-muted-foreground">
          Sales, profitability, and inventory performance over the last 30 days.
        </p>
      </div>

      <Suspense fallback={<DashboardSkeleton />}>
        <DashboardContent />
      </Suspense>
    </div>
  );
}
