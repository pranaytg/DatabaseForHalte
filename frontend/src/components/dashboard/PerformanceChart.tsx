"use client";

import { useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { OrderProfitability } from "@/types/dashboard";
import { formatCurrency } from "@/lib/utils";

export function PerformanceChart({ data }: { data: OrderProfitability[] }) {
  // Aggregate daily revenue & profit
  const chartData = useMemo(() => {
    const dailyMap = new Map<
      string,
      { date: string; gross: number; net: number }
    >();

    data.forEach((order) => {
      // Use just the date part "YYYY-MM-DD"
      const dateStr = order.purchase_date.split("T")[0];
      const existing = dailyMap.get(dateStr) || {
        date: dateStr,
        gross: 0,
        net: 0,
      };

      existing.gross += order.line_item_revenue || 0;
      existing.net += order.net_profit || 0;

      dailyMap.set(dateStr, existing);
    });

    // Convert map to array and sort chronologically
    return Array.from(dailyMap.values()).sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime(),
    );
  }, [data]);

  return (
    <Card className="col-span-full">
      <CardHeader>
        <CardTitle>Performance Over Time</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[350px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={chartData}
              margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                vertical={false}
                stroke="#e5e7eb"
              />
              <XAxis
                dataKey="date"
                tickLine={false}
                axisLine={false}
                tickFormatter={(value) => {
                  const d = new Date(value);
                  return `${d.getDate()} ${d.toLocaleString("default", { month: "short" })}`;
                }}
              />
              <YAxis
                tickLine={false}
                axisLine={false}
                tickFormatter={(value) => `₹${(value / 1000).toFixed(0)}k`}
              />
              <Tooltip
                formatter={(value) => formatCurrency(Number(value ?? 0))}
                labelFormatter={(label) =>
                  new Date(label as string).toLocaleDateString()
                }
              />
              <Legend />
              <Line
                type="monotone"
                name="Gross Revenue"
                dataKey="gross"
                stroke="#3b82f6" // blue-500
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                name="Net Profit"
                dataKey="net"
                stroke="#16a34a" // green-600
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
