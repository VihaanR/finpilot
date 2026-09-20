"use client";

import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import { ChartWithTable } from "@/components/charts/ChartWithTable";
import { CitationChip } from "@/components/citations/CitationChip";
import { Money } from "@/components/ui/Money";
import { compactPaise } from "@/lib/format";
import type { CategorySlice } from "@/lib/types";

/** Sequential, not categorical: the bars encode one quantity, not identity. */
const RAMP = [
  "var(--primary)",
  "color-mix(in srgb, var(--primary) 82%, var(--accent))",
  "color-mix(in srgb, var(--primary) 64%, var(--accent))",
  "color-mix(in srgb, var(--primary) 46%, var(--accent))",
  "var(--accent)",
];

export function CategoryChart({ categories }: { categories: CategorySlice[] }) {
  const top = categories.slice(0, 8);
  const total = categories.reduce((sum, c) => sum + c.amount_paise, 0);

  return (
    <ChartWithTable
      title="Where the money went"
      description="Spending by category this month, largest first."
      rows={top}
      rowKey={(row) => row.category_slug}
      rowHeader={{
        header: "Category",
        cell: (row) => row.category_name,
      }}
      columns={[
        {
          key: "amount",
          header: "Amount",
          numeric: true,
          cell: (row) => (
            <CitationChip
              paise={row.amount_paise}
              txnIds={row.txn_ids}
              title={row.category_name}
              subtitle="Transactions in this category this month"
            />
          ),
        },
        {
          key: "share",
          header: "Share",
          numeric: true,
          cell: (row) =>
            total > 0 ? `${Math.round((row.amount_paise / total) * 100)}%` : "—",
        },
      ]}
    >
      <ResponsiveContainer width="100%" height={Math.max(220, top.length * 38)}>
        <BarChart data={top} layout="vertical" margin={{ left: 0, right: 16 }}>
          <XAxis
            type="number"
            tickFormatter={(v) => compactPaise(Number(v))}
            stroke="var(--fg-subtle)"
            fontSize={12}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            type="category"
            dataKey="category_name"
            width={120}
            stroke="var(--fg-muted)"
            fontSize={12}
            tickLine={false}
            axisLine={false}
          />
          <Bar dataKey="amount_paise" radius={[0, 6, 6, 0]} isAnimationActive={false}>
            {top.map((row, i) => (
              <Cell key={row.category_slug} fill={RAMP[Math.min(i, RAMP.length - 1)]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p className="mt-2 text-sm text-[var(--fg-muted)]">
        Largest: {top[0]?.category_name ?? "—"} at{" "}
        {top[0] ? <Money paise={top[0].amount_paise} /> : "—"}.
      </p>
    </ChartWithTable>
  );
}
