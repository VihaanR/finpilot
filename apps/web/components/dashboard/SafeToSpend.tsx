"use client";

import { GlassPanel } from "@/components/ui/Glass";
import { Money } from "@/components/ui/Money";
import { Pill } from "@/components/ui/Badge";
import { CitationChip } from "@/components/citations/CitationChip";
import { formatDate, formatDayMonth } from "@/lib/format";
import type { SafeToSpend as SafeToSpendData } from "@/lib/types";

/**
 * The hero figure.
 *
 * "Committed" here means obligations due strictly before the next income date
 * (DESIGN.md 8.3). It is deliberately not "everything you pay in a month" —
 * mandates that already fired this month are not money you still owe.
 */
export function SafeToSpend({ data }: { data: SafeToSpendData }) {
  const obligationIds = data.citations.flatMap((c) => c.txn_ids);

  return (
    <GlassPanel strong className="p-6 sm:p-8">
      <p className="text-xs uppercase tracking-[0.18em] text-[var(--accent)]">
        Safe to spend
      </p>

      <p className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <Money
          paise={data.safe_daily_paise}
          className="font-[family-name:var(--font-display)] text-5xl tracking-tight text-[var(--fg)] sm:text-6xl"
        />
        <span className="text-lg text-[var(--fg-muted)]">per day</span>
      </p>

      <p className="mt-4 max-w-2xl text-[var(--fg-muted)]">
        {data.committed_paise > 0 ? (
          <>
            <CitationChip
              paise={data.committed_paise}
              txnIds={obligationIds}
              title="Committed before your next income"
              subtitle={`${data.obligations.length} obligation${data.obligations.length === 1 ? "" : "s"} due before ${data.next_income_date ? formatDate(data.next_income_date) : "your next income"}`}
              className="font-medium text-[var(--fg)]"
            />{" "}
            is already committed over the next{" "}
            <span className="tnum font-medium text-[var(--fg)]">
              {data.days_remaining}
            </span>{" "}
            days.
          </>
        ) : (
          <>Nothing is committed before your next income.</>
        )}{" "}
        {data.next_income_date ? (
          <>
            Your next income of{" "}
            <Money paise={data.next_income_paise} className="font-medium text-[var(--fg)]" />{" "}
            is expected on {formatDate(data.next_income_date)}.
          </>
        ) : null}
      </p>

      <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
        <Stat label="In your accounts" paise={data.current_balance_paise} />
        <Stat label="Committed" paise={data.committed_paise} />
        <Stat label="Set aside for goals" paise={data.goal_due_paise} />
        <Stat label="Left to spend" paise={data.discretionary_paise} />
      </dl>

      {data.obligations.length > 0 ? (
        <div className="mt-6">
          <h3 className="mb-2 text-sm font-medium text-[var(--fg)]">
            Due before then
          </h3>
          <ul className="divide-y divide-[var(--border)]">
            {data.obligations.map((o) => (
              <li
                key={o.series_key + o.due_date}
                className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-2"
              >
                <span className="flex flex-wrap items-center gap-2">
                  <span className="text-sm text-[var(--fg)]">
                    {o.normalized_merchant}
                  </span>
                  {o.afa_band === "SILENT" ? (
                    <Pill tone="warn">No OTP</Pill>
                  ) : null}
                </span>
                <span className="flex items-baseline gap-3 text-sm">
                  <span className="text-[var(--fg-muted)]">
                    {formatDayMonth(o.due_date)}
                  </span>
                  <Money paise={o.amount_paise} className="font-medium" />
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </GlassPanel>
  );
}

function Stat({ label, paise }: { label: string; paise: number }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wider text-[var(--fg-subtle)]">
        {label}
      </dt>
      <dd className="mt-1">
        <Money paise={paise} className="text-lg font-medium text-[var(--fg)]" />
      </dd>
    </div>
  );
}
