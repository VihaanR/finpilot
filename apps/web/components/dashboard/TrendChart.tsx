"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import { ChartWithTable } from "@/components/charts/ChartWithTable";
import { Money } from "@/components/ui/Money";
import { compactPaise, formatMonth } from "@/lib/format";
import type { MonthSummary } from "@/lib/types";

export function TrendChart({ trend }: { trend: MonthSummary[] }) {
  const rows = trend.map((m) => ({ ...m, label: formatMonth(m.month, "short") }));

  return (
    <ChartWithTable
      title="Income against spending"
      description="The last six complete months."
      rows={rows}
      rowKey={(row) => row.month}
      rowHeader={{ header: "Month", cell: (row) => row.label }}
      columns={[
        {
          key: "income",
          header: "Income",
          numeric: true,
          cell: (row) => <Money paise={row.income_paise} />,
        },
        {
          key: "expense",
          header: "Spending",
          numeric: true,
          cell: (row) => <Money paise={row.expense_paise} />,
        },
        {
          key: "net",
          header: "Net",
          numeric: true,
          cell: (row) => (
            <Money
              paise={row.net_paise}
              signed
              tone={row.net_paise >= 0 ? "positive" : "critical"}
            />
          ),
        },
      ]}
    >
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={rows} margin={{ left: 0, right: 8, top: 8 }}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="label"
            stroke="var(--fg-subtle)"
            fontSize={12}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            tickFormatter={(v) => compactPaise(Number(v))}
            stroke="var(--fg-subtle)"
            fontSize={12}
            tickLine={false}
            axisLine={false}
            width={56}
          />
          <Legend
            wrapperStyle={{ fontSize: 12, color: "var(--fg-muted)" }}
            iconType="plainline"
          />
          {/* Dash pattern as well as colour, so the two lines stay
              distinguishable in greyscale. */}
          <Line
            type="monotone"
            dataKey="income_paise"
            name="Income"
            stroke="var(--primary)"
            strokeWidth={2}
            dot={{ r: 3 }}
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="expense_paise"
            name="Spending"
            stroke="var(--accent)"
            strokeWidth={2}
            strokeDasharray="5 3"
            dot={{ r: 3 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartWithTable>
  );
}
