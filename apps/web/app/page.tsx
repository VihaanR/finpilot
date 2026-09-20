"use client";

import Link from "next/link";
import { GlassPanel, SectionHeading } from "@/components/ui/Glass";
import { Money } from "@/components/ui/Money";
import { ErrorPanel, LoadingPanel, EmptyPanel } from "@/components/ui/States";
import { SafeToSpend } from "@/components/dashboard/SafeToSpend";
import { LeakGauge } from "@/components/dashboard/LeakGauge";
import { CategoryChart } from "@/components/dashboard/CategoryChart";
import { TrendChart } from "@/components/dashboard/TrendChart";
import { AnomalyCards } from "@/components/dashboard/AnomalyCards";
import { CitationChip } from "@/components/citations/CitationChip";
import { useApi } from "@/lib/useApi";
import { formatDate, formatMonth } from "@/lib/format";
import type { Dashboard } from "@/lib/types";

export default function DashboardPage() {
  const { data, error, loading, reload } = useApi<Dashboard>("/api/dashboard");

  return (
    <div className="mx-auto w-full max-w-6xl space-y-8">
      <div>
        <SectionHeading
          as="h1"
          hint={data ? `As of ${formatDate(data.as_of)}` : undefined}
        >
          Your money, explained
        </SectionHeading>
        <p className="max-w-2xl text-[var(--fg-muted)]">
          Every figure here is computed by a deterministic engine, and every one
          of them opens to the transactions underneath it.
        </p>
      </div>

      {loading && !data ? <LoadingPanel label="Loading your ledger…" /> : null}
      {error ? <ErrorPanel message={error} /> : null}

      {data && data.transaction_count === 0 ? (
        <EmptyPanel title="No transactions yet" />
      ) : null}

      {data && data.transaction_count > 0 ? (
        <>
          <SafeToSpend data={data.safe_to_spend} />

          <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
            <div className="space-y-6">
              <GlassPanel className="p-6">
                <SectionHeading hint={formatMonth(data.month.month)}>
                  This month
                </SectionHeading>
                <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
                  <Stat label="Income" paise={data.month.income_paise} />
                  <Stat label="Spending" paise={data.month.expense_paise} />
                  <Stat
                    label="Net"
                    paise={data.month.net_paise}
                    signed
                    tone={data.month.net_paise >= 0 ? "positive" : "critical"}
                  />
                  <div>
                    <dt className="text-xs uppercase tracking-wider text-[var(--fg-subtle)]">
                      Transactions
                    </dt>
                    <dd className="tnum mt-1 text-lg font-medium text-[var(--fg)]">
                      {data.month.txn_count ?? "—"}
                    </dd>
                  </div>
                </dl>
              </GlassPanel>

              <GlassPanel className="p-6">
                <TrendChart trend={data.trend} />
              </GlassPanel>

              <GlassPanel className="p-6">
                <CategoryChart categories={data.categories} />
              </GlassPanel>
            </div>

            <div className="space-y-6">
              <LeakGauge leak={data.leak_score} />

              <GlassPanel className="p-6">
                <SectionHeading>Accounts</SectionHeading>
                <ul className="space-y-3">
                  {data.accounts.map((a) => (
                    <li key={a.id} className="flex items-baseline justify-between gap-3">
                      <span>
                        <span className="block text-sm text-[var(--fg)]">
                          {a.display_name}
                        </span>
                        <span className="block text-xs text-[var(--fg-subtle)]">
                          {a.account_type.replace("_", " ").toLowerCase()} ····{a.last4}
                        </span>
                      </span>
                      <Money
                        paise={a.current_balance_paise}
                        className="text-sm font-medium"
                      />
                    </li>
                  ))}
                </ul>
                <p className="mt-4 border-t border-[var(--border)] pt-3 text-sm">
                  <span className="text-[var(--fg-muted)]">Liquid balance: </span>
                  <Money paise={data.balance_paise} className="font-medium" />
                </p>
                <p className="mt-1 text-xs leading-relaxed text-[var(--fg-subtle)]">
                  Credit card outstanding is excluded: it is money owed, not
                  money you hold.
                </p>
              </GlassPanel>

              {data.budgets.length > 0 ? (
                <GlassPanel className="p-6">
                  <SectionHeading>Budgets</SectionHeading>
                  <ul className="space-y-3">
                    {data.budgets.map((b) => (
                      <li key={b.category_slug}>
                        <div className="flex items-baseline justify-between gap-3 text-sm">
                          <CitationChip
                            txnIds={b.txn_ids}
                            title={b.category_name}
                            subtitle="Transactions against this budget"
                            className="text-[var(--fg)]"
                          >
                            <span>{b.category_name}</span>
                          </CitationChip>
                          <span className="tnum text-[var(--fg-muted)]">
                            {Math.round(b.pct_used)}% used
                          </span>
                        </div>
                        <div
                          className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-[var(--border-strong)]"
                          role="img"
                          aria-label={`${b.category_name}: ${Math.round(b.pct_used)} percent of budget used, pacing ${b.pace.toLowerCase().replace("_", " ")}`}
                        >
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${Math.min(100, b.pct_used)}%`,
                              background:
                                b.pct_used > 100
                                  ? "var(--critical)"
                                  : "var(--primary)",
                            }}
                          />
                        </div>
                        <p className="mt-1 text-xs text-[var(--fg-subtle)]">
                          <Money paise={b.spent_paise} /> of{" "}
                          <Money paise={b.limit_paise} /> ·{" "}
                          {b.pace.toLowerCase().replace(/_/g, " ")}
                        </p>
                      </li>
                    ))}
                  </ul>
                </GlassPanel>
              ) : null}

              <GlassPanel className="p-6">
                <SectionHeading>Next</SectionHeading>
                <p className="text-sm text-[var(--fg-muted)]">
                  The Mandate Radar shows what will debit over the next 30 days,
                  and which of those will go through without asking you.
                </p>
                <Link
                  href="/radar"
                  className="mt-3 inline-block rounded-full border border-[var(--border-strong)] px-4 py-2 text-sm text-[var(--fg)] hover:bg-[var(--primary-soft)]"
                >
                  Open Mandate Radar
                </Link>
              </GlassPanel>
            </div>
          </div>

          <AnomalyCards anomalies={data.anomalies} onDismissed={reload} />
        </>
      ) : null}
    </div>
  );
}

function Stat({
  label,
  paise,
  signed,
  tone,
}: {
  label: string;
  paise: number;
  signed?: boolean;
  tone?: "positive" | "critical";
}) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wider text-[var(--fg-subtle)]">
        {label}
      </dt>
      <dd className="mt-1">
        <Money
          paise={paise}
          signed={signed}
          tone={tone}
          className="text-lg font-medium"
        />
      </dd>
    </div>
  );
}
