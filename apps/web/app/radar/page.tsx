"use client";

import { useState } from "react";
import { GlassPanel, SectionHeading } from "@/components/ui/Glass";
import { Button } from "@/components/ui/Button";
import { Money } from "@/components/ui/Money";
import { Pill, RuleBadge } from "@/components/ui/Badge";
import { CitationChip } from "@/components/citations/CitationChip";
import { LeakGauge } from "@/components/dashboard/LeakGauge";
import { RevokeKit } from "@/components/radar/RevokeKit";
import { ErrorPanel, LoadingPanel, EmptyPanel } from "@/components/ui/States";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { formatDate, formatDayMonth } from "@/lib/format";
import type { Radar } from "@/lib/types";

export default function RadarPage() {
  const { data, error, loading, reload } = useApi<Radar>("/api/radar");
  const [openKit, setOpenKit] = useState<string | null>(null);
  const [notice, setNotice] = useState("");

  async function acknowledge(key: string, acknowledged: boolean) {
    try {
      const r = await api.post<{ silent_mandate_cleared: boolean }>(
        `/api/radar/${encodeURIComponent(key)}/acknowledge`,
        { acknowledged },
      );
      setNotice(
        acknowledged
          ? r.silent_mandate_cleared
            ? "Marked as known. It no longer counts as a silent mandate."
            : "Marked as known."
          : "Moved back to unknown.",
      );
      reload();
    } catch (e) {
      setNotice((e as Error).message);
    }
  }

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6">
      <div>
        <SectionHeading
          as="h1"
          hint={data ? `Next ${data.horizon_days} days from ${formatDate(data.as_of)}` : undefined}
        >
          Mandate Radar
        </SectionHeading>
        <p className="max-w-3xl text-[var(--fg-muted)]">
          Under RBI&rsquo;s e-mandate framework, recurring debits up to ₹15,000
          go through with no OTP at all — ₹1 lakh for insurance premiums, SIPs
          and credit-card bills. Everything marked <em>Silent</em> below will
          leave your account without asking you.
        </p>
      </div>

      {error ? <ErrorPanel message={error} /> : null}
      {loading && !data ? <LoadingPanel label="Reading your mandates…" /> : null}

      <p aria-live="polite" className="text-sm text-[var(--positive)]">
        {notice}
      </p>

      {data ? (
        <>
          {data.banner.count > 0 ? (
            <GlassPanel
              strong
              className="border-[var(--caution)] p-6"
              role="region"
              aria-label="Debits due within seven days"
            >
              <p className="text-xs uppercase tracking-[0.18em] text-[var(--caution)]">
                <span aria-hidden="true">● </span>
                Next {data.banner_days} days
              </p>
              <p className="mt-2 text-lg text-[var(--fg)]">
                <span className="tnum font-medium">{data.banner.count}</span>{" "}
                debit{data.banner.count === 1 ? "" : "s"} totalling{" "}
                <Money paise={data.banner.total_paise} className="font-medium" />{" "}
                will fire before this time next week.
              </p>
              <ul className="mt-3 flex flex-wrap gap-2">
                {data.banner.items.map((i) => (
                  <li key={i.series_key}>
                    <Pill tone={i.afa_band === "SILENT" ? "warn" : "info"}>
                      {i.merchant} · {formatDayMonth(i.due_date)}
                    </Pill>
                  </li>
                ))}
              </ul>
            </GlassPanel>
          ) : null}

          <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
            <div className="space-y-6">
              <section aria-labelledby="timeline-heading">
                <SectionHeading id="timeline-heading">
                  The next 30 days
                </SectionHeading>

                {data.weeks.every((w) => w.items.length === 0) ? (
                  <EmptyPanel title="Nothing scheduled">
                    No recurring debit is expected in the next 30 days.
                  </EmptyPanel>
                ) : (
                  <ol className="space-y-4">
                    {data.weeks.map((week) => (
                      <li key={week.week}>
                        <GlassPanel className="p-5">
                          <div className="mb-3 flex flex-wrap items-baseline justify-between gap-3">
                            <h3 className="font-[family-name:var(--font-display)] text-base text-[var(--fg)]">
                              Week {week.week} · from {formatDayMonth(week.starts_on)}
                            </h3>
                            <Money
                              paise={week.total_paise}
                              className="text-sm font-medium text-[var(--fg-muted)]"
                            />
                          </div>

                          {week.items.length === 0 ? (
                            <p className="text-sm text-[var(--fg-subtle)]">
                              Nothing expected this week.
                            </p>
                          ) : (
                            <ul className="divide-y divide-[var(--border)]">
                              {week.items.map((item) => (
                                <li
                                  key={item.series_key + item.due_date}
                                  className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 py-3"
                                >
                                  <div className="min-w-0">
                                    <p className="text-sm text-[var(--fg)]">
                                      {item.merchant}
                                      {item.acknowledged ? (
                                        <span className="ml-2 text-xs text-[var(--fg-subtle)]">
                                          (you know about this)
                                        </span>
                                      ) : null}
                                    </p>
                                    <p className="mt-0.5 text-xs text-[var(--fg-subtle)]">
                                      {item.category_name} ·{" "}
                                      {formatDate(item.due_date)} · in{" "}
                                      {item.days_away} day
                                      {item.days_away === 1 ? "" : "s"}
                                    </p>
                                    <ul className="mt-1.5 flex flex-wrap gap-1.5">
                                      {item.badges.map((b) => (
                                        <li key={b.code}>
                                          <RuleBadge badge={b} />
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                  <Money
                                    paise={item.amount_paise}
                                    className="text-sm font-medium"
                                  />
                                </li>
                              ))}
                            </ul>
                          )}
                        </GlassPanel>
                      </li>
                    ))}
                  </ol>
                )}
              </section>

              <section aria-labelledby="series-heading">
                <SectionHeading
                  id="series-heading"
                  hint={`${data.series.length} detected`}
                >
                  Every recurring commitment
                </SectionHeading>

                <ul className="space-y-3">
                  {data.series.map((s) => (
                    <li key={s.key}>
                      <GlassPanel className="p-5">
                        <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
                          <div className="min-w-0">
                            <h3 className="text-sm font-medium text-[var(--fg)]">
                              {s.normalized_merchant}
                            </h3>
                            <p className="mt-0.5 text-xs text-[var(--fg-subtle)]">
                              {s.category_name} ·{" "}
                              {s.cadence.toLowerCase()} · {s.status.toLowerCase()} ·{" "}
                              seen {s.occurrence_count} times
                              {s.next_expected_date
                                ? ` · next ${formatDate(s.next_expected_date)}`
                                : ""}
                            </p>
                            <ul className="mt-2 flex flex-wrap gap-1.5">
                              {s.badges.map((b) => (
                                <li key={b.code}>
                                  <RuleBadge badge={b} />
                                </li>
                              ))}
                            </ul>
                          </div>
                          <CitationChip
                            paise={s.median_amount_paise}
                            txnIds={s.txn_ids}
                            title={s.normalized_merchant}
                            subtitle={`Every charge in this ${s.cadence.toLowerCase()} series`}
                            className="text-sm font-medium"
                          />
                        </div>

                        <div className="mt-3 flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            onClick={() => acknowledge(s.key, !s.acknowledged)}
                          >
                            {s.acknowledged
                              ? "I did not know about this"
                              : "I know about this"}
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            aria-expanded={openKit === s.key}
                            onClick={() =>
                              setOpenKit((k) => (k === s.key ? null : s.key))
                            }
                          >
                            {openKit === s.key ? "Hide revoke kit" : "How do I stop it?"}
                          </Button>
                        </div>

                        {openKit === s.key ? (
                          <RevokeKit kit={s.revoke_kit} merchant={s.normalized_merchant} />
                        ) : null}
                      </GlassPanel>
                    </li>
                  ))}
                </ul>
              </section>
            </div>

            <div className="space-y-6">
              <LeakGauge leak={data.leak_score} />

              <GlassPanel className="p-6">
                <SectionHeading>What the badges mean</SectionHeading>
                <dl className="space-y-2 text-sm">
                  <Definition term="Silent">
                    Debits without an OTP, because it is under the RBI e-mandate
                    threshold.
                  </Definition>
                  <Definition term="High limit">
                    Insurance, SIPs and credit-card bills debit without an OTP
                    up to ₹1 lakh, not ₹15,000.
                  </Definition>
                  <Definition term="Price up">
                    This charge has risen since it started.
                  </Definition>
                  <Definition term="Duplicate">
                    You pay another service of the same kind.
                  </Definition>
                  <Definition term="Trial to paid">
                    It started near zero and then rose to full price.
                  </Definition>
                  <Definition term="Dormant">
                    It keeps charging but nothing suggests you still use it.
                  </Definition>
                </dl>
              </GlassPanel>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}

function Definition({
  term,
  children,
}: {
  term: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <dt className="font-medium text-[var(--fg)]">{term}</dt>
      <dd className="text-[var(--fg-muted)]">{children}</dd>
    </div>
  );
}
