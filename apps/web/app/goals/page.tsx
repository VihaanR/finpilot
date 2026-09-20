"use client";

import { useState } from "react";
import { GlassPanel, SectionHeading } from "@/components/ui/Glass";
import { Button } from "@/components/ui/Button";
import { Money } from "@/components/ui/Money";
import { Pill } from "@/components/ui/Badge";
import { ErrorPanel, LoadingPanel, EmptyPanel } from "@/components/ui/States";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { formatDate, titleCase } from "@/lib/format";
import type { GoalsView, SimulationResult } from "@/lib/types";

const VERDICT_TONE = {
  AHEAD: "info",
  ON_TRACK: "info",
  BEHIND: "warn",
  UNREACHABLE: "alert",
} as const;

function monthName(iso: string | null) {
  if (!iso) return "never at this rate";
  return new Date(iso + "T00:00:00").toLocaleDateString("en-IN", {
    month: "long",
    year: "numeric",
  });
}

export default function GoalsPage() {
  const { data, error, loading } = useApi<GoalsView>("/api/goals");
  const [cancelled, setCancelled] = useState<string[]>([]);
  const [pct, setPct] = useState<Record<string, number>>({});
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [simError, setSimError] = useState("");

  async function simulate() {
    setBusy(true);
    setSimError("");
    try {
      const r = await api.post<SimulationResult>("/api/simulate", {
        cancel_series: cancelled,
        category_pct_change: Object.fromEntries(
          Object.entries(pct).filter(([, v]) => v !== 0),
        ),
      });
      setResult(r);
    } catch (e) {
      setSimError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setCancelled([]);
    setPct({});
    setResult(null);
  }

  const sliderCategories = (data?.categories ?? []).slice(0, 8);

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6">
      <div>
        <SectionHeading as="h1" hint={data ? `As of ${formatDate(data.as_of)}` : undefined}>
          Goals and what-ifs
        </SectionHeading>
        <p className="max-w-3xl text-[var(--fg-muted)]">
          Every date below is arithmetic on your own ledger. Change something on
          the right and watch the dates move.
        </p>
      </div>

      {error ? <ErrorPanel message={error} /> : null}
      {loading && !data ? <LoadingPanel label="Projecting your goals…" /> : null}

      {data ? (
        <div className="grid gap-6 lg:grid-cols-[1fr_24rem]">
          <div className="space-y-6">
            <GlassPanel className="p-5">
              <p className="text-sm text-[var(--fg-muted)]">
                Measured monthly surplus:{" "}
                <Money
                  paise={data.monthly_surplus_paise}
                  signed
                  tone={data.monthly_surplus_paise >= 0 ? "positive" : "critical"}
                  className="font-medium"
                />
              </p>
              {data.monthly_surplus_paise < 0 ? (
                <p className="mt-1 text-xs leading-relaxed text-[var(--fg-subtle)]">
                  Your recent months spend more than they take in, so goals fed
                  only by surplus cannot reach their targets. Cancelling
                  commitments on the right is what changes this.
                </p>
              ) : null}
            </GlassPanel>

            {data.goals.length === 0 ? (
              <EmptyPanel title="No goals set">
                Goals arrive with the demo ledger, or with a statement that has
                them.
              </EmptyPanel>
            ) : (
              <ul className="space-y-4">
                {data.goals.map((g) => {
                  const simulated = result?.goals.find((x) => x.goal_id === g.goal_id);
                  const progress =
                    g.target_paise > 0
                      ? Math.min(100, (g.current_paise / g.target_paise) * 100)
                      : 0;
                  return (
                    <li key={g.goal_id}>
                      <GlassPanel className="p-6">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <h2 className="font-[family-name:var(--font-display)] text-xl text-[var(--fg)]">
                            {g.name}
                          </h2>
                          <Pill tone={VERDICT_TONE[g.verdict] ?? "muted"}>
                            {titleCase(g.verdict)}
                          </Pill>
                        </div>

                        <p className="mt-2 text-sm text-[var(--fg-muted)]">
                          <Money paise={g.current_paise} className="font-medium text-[var(--fg)]" />{" "}
                          of <Money paise={g.target_paise} /> by{" "}
                          {formatDate(g.target_date)}.{" "}
                          <Money paise={g.shortfall_paise} /> still to go.
                        </p>

                        <div
                          className="mt-3 h-2 w-full overflow-hidden rounded-full bg-[var(--border-strong)]"
                          role="img"
                          aria-label={`${g.name} is ${Math.round(progress)} percent funded`}
                        >
                          <div
                            className="h-full rounded-full bg-[var(--primary)]"
                            style={{ width: `${progress}%` }}
                          />
                        </div>

                        <dl className="mt-4 grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
                          <div>
                            <dt className="text-xs uppercase tracking-wider text-[var(--fg-subtle)]">
                              Needed monthly
                            </dt>
                            <dd className="mt-0.5">
                              <Money paise={g.required_monthly_paise} />
                            </dd>
                          </div>
                          <div>
                            <dt className="text-xs uppercase tracking-wider text-[var(--fg-subtle)]">
                              Currently allocated
                            </dt>
                            <dd className="mt-0.5">
                              <Money paise={g.allocated_monthly_paise} />
                            </dd>
                          </div>
                          <div>
                            <dt className="text-xs uppercase tracking-wider text-[var(--fg-subtle)]">
                              Projected arrival
                            </dt>
                            <dd className="mt-0.5 text-[var(--fg)]">
                              {monthName(g.projected_eta)}
                            </dd>
                          </div>
                        </dl>

                        {simulated ? (
                          <p className="mt-4 rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--accent-soft)] p-3 text-sm text-[var(--fg)]">
                            <span className="font-medium">With your changes: </span>
                            {monthName(simulated.eta_before)} →{" "}
                            <span className="font-medium">
                              {monthName(simulated.eta_after)}
                            </span>
                            {simulated.months_delta !== 0 ? (
                              <>
                                {" "}
                                ({Math.abs(simulated.months_delta)} month
                                {Math.abs(simulated.months_delta) === 1 ? "" : "s"}{" "}
                                {simulated.months_delta > 0 ? "earlier" : "later"})
                              </>
                            ) : null}
                          </p>
                        ) : null}
                      </GlassPanel>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          <aside aria-labelledby="sim-heading" className="space-y-4">
            <GlassPanel className="p-6">
              <SectionHeading id="sim-heading">What if…</SectionHeading>

              <fieldset className="mt-2">
                <legend className="text-sm font-medium text-[var(--fg)]">
                  I cancelled these
                </legend>
                <ul className="mt-2 max-h-64 space-y-1.5 overflow-y-auto pr-1">
                  {data.cancellable_series.map((s) => (
                    <li key={s.series_key}>
                      <label className="flex items-start gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={cancelled.includes(s.series_key)}
                          onChange={(e) =>
                            setCancelled((prev) =>
                              e.target.checked
                                ? [...prev, s.series_key]
                                : prev.filter((k) => k !== s.series_key),
                            )
                          }
                          className="mt-0.5 h-4 w-4 accent-[var(--primary)]"
                        />
                        <span>
                          <span className="text-[var(--fg)]">{s.merchant}</span>
                          <span className="block text-xs text-[var(--fg-subtle)]">
                            <Money paise={s.monthly_paise} /> a month ·{" "}
                            {s.category_name}
                          </span>
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
              </fieldset>

              <fieldset className="mt-5">
                <legend className="text-sm font-medium text-[var(--fg)]">
                  I changed these by
                </legend>
                <div className="mt-2 space-y-3">
                  {sliderCategories.map((slug) => {
                    const value = pct[slug] ?? 0;
                    return (
                      <div key={slug}>
                        <label
                          htmlFor={`pct-${slug}`}
                          className="flex items-baseline justify-between text-sm"
                        >
                          <span className="text-[var(--fg)]">{titleCase(slug)}</span>
                          <span className="tnum text-[var(--fg-muted)]">
                            {value > 0 ? "+" : ""}
                            {value}%
                          </span>
                        </label>
                        <input
                          id={`pct-${slug}`}
                          type="range"
                          min={-50}
                          max={50}
                          step={5}
                          value={value}
                          aria-valuetext={`${titleCase(slug)} ${value === 0 ? "unchanged" : `${value > 0 ? "up" : "down"} ${Math.abs(value)} percent`}`}
                          onChange={(e) =>
                            setPct((prev) => ({ ...prev, [slug]: Number(e.target.value) }))
                          }
                          className="mt-1 w-full accent-[var(--primary)]"
                        />
                      </div>
                    );
                  })}
                </div>
              </fieldset>

              <div className="mt-5 flex flex-wrap gap-2">
                <Button variant="primary" onClick={simulate} disabled={busy}>
                  {busy ? "Working it out…" : "Run the scenario"}
                </Button>
                <Button variant="ghost" onClick={reset}>
                  Reset
                </Button>
              </div>

              {simError ? (
                <p role="alert" className="mt-3 text-sm text-[var(--critical)]">
                  {simError}
                </p>
              ) : null}
            </GlassPanel>

            {result ? (
              <GlassPanel strong className="p-6" aria-live="polite">
                <SectionHeading>The result</SectionHeading>
                <p className="text-sm leading-relaxed text-[var(--fg-muted)]">
                  Cancelling{" "}
                  <span className="font-medium text-[var(--fg)]">
                    {result.narration_facts.cancelled_count}
                  </span>{" "}
                  commitment
                  {result.narration_facts.cancelled_count === 1 ? "" : "s"} frees{" "}
                  <Money
                    paise={result.cancelled_monthly_paise}
                    className="font-medium text-[var(--fg)]"
                  />{" "}
                  a month. Your monthly surplus moves from{" "}
                  <Money paise={result.monthly_surplus_before_paise} signed /> to{" "}
                  <Money
                    paise={result.monthly_surplus_after_paise}
                    signed
                    className="font-medium"
                    tone={
                      result.monthly_surplus_after_paise >= 0
                        ? "positive"
                        : "critical"
                    }
                  />
                  .
                </p>
                <p className="mt-3 text-xs leading-relaxed text-[var(--fg-subtle)]">
                  These are arithmetic outcomes on your own ledger, not a
                  recommendation to cancel anything.
                </p>
              </GlassPanel>
            ) : null}
          </aside>
        </div>
      ) : null}
    </div>
  );
}
