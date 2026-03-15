import { Suspense } from "react";
import { ProfitabilityTable } from "@/components/profitability/ProfitabilityTable";
import { fetchApi } from "@/lib/api";
import { SkuProfitabilityResponse } from "@/types/profitability";

export const dynamic = "force-dynamic";

function ProfitabilitySkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-[600px] rounded-xl bg-muted" />
    </div>
  );
}

async function ProfitabilityContent() {
  // Fetch SKU profitability data (sorted by net profit by default from the DB view)
  const data = await fetchApi<SkuProfitabilityResponse>(
    "profitability/sku?limit=500",
    {
      cache: "no-store",
    },
  );

  return (
    <div className="space-y-6">
      <ProfitabilityTable data={data.sku_profitability} />
    </div>
  );
}

export default function ProfitabilityPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">
          Profitability & COGS Editor
        </h2>
        <p className="text-muted-foreground">
          Track Net Profit by SKU and manage your Cost of Goods Sold.
        </p>
      </div>

      <Suspense fallback={<ProfitabilitySkeleton />}>
        <ProfitabilityContent />
      </Suspense>
    </div>
  );
}
