"use client";

import { useState } from "react";
import { GlassPanel, SectionHeading } from "@/components/ui/Glass";
import { Button } from "@/components/ui/Button";
import { Pill } from "@/components/ui/Badge";
import { CitationChip } from "@/components/citations/CitationChip";
import { api } from "@/lib/api";
import { titleCase } from "@/lib/format";
import type { Anomaly } from "@/lib/types";

const SEVERITY_TONE = { HIGH: "alert", MEDIUM: "warn", LOW: "info" } as const;

export function AnomalyCards({
  anomalies,
  onDismissed,
}: {
  anomalies: Anomaly[];
  onDismissed: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [status, setStatus] = useState("");

  async function dismiss(anomaly: Anomaly) {
    setBusy(anomaly.key);
    try {
      await api.post(`/api/anomalies/${encodeURIComponent(anomaly.key)}/dismiss`);
      setStatus(`Dismissed: ${anomaly.explanation.slice(0, 60)}…`);
      onDismissed();
    } catch (e) {
      setStatus((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  if (!anomalies.length) {
    return (
      <GlassPanel className="p-6">
        <SectionHeading>Worth a look</SectionHeading>
        <p className="text-sm text-[var(--fg-muted)]">
          Nothing unusual in this period. Spikes, duplicate charges, price rises
          and unfamiliar large merchants would appear here.
        </p>
      </GlassPanel>
    );
  }

  return (
    <section aria-labelledby="anomalies-heading">
      <SectionHeading
        id="anomalies-heading"
        hint={`${anomalies.length} flagged`}
      >
        Worth a look
      </SectionHeading>

      <p aria-live="polite" className="sr-only">
        {status}
      </p>

      <ul className="grid gap-3 sm:grid-cols-2">
        {anomalies.map((a) => (
          <li key={a.key}>
            <GlassPanel className="flex h-full flex-col gap-3 p-5">
              <div className="flex flex-wrap items-center gap-2">
                <Pill tone={SEVERITY_TONE[a.severity] ?? "info"}>
                  {titleCase(a.type)}
                </Pill>
                <span className="text-xs uppercase tracking-wider text-[var(--fg-subtle)]">
                  {a.severity.toLowerCase()} severity
                </span>
              </div>

              <p className="flex-1 text-sm leading-relaxed text-[var(--fg)]">
                {a.explanation}
              </p>

              <div className="flex flex-wrap items-center gap-3">
                {a.txn_ids.length > 0 ? (
                  <CitationChip
                    txnIds={a.txn_ids}
                    title={titleCase(a.type)}
                    subtitle={a.explanation}
                    className="text-sm text-[var(--fg-muted)]"
                  >
                    <span>
                      See {a.txn_ids.length} transaction
                      {a.txn_ids.length === 1 ? "" : "s"}
                    </span>
                  </CitationChip>
                ) : null}
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={busy === a.key}
                  onClick={() => dismiss(a)}
                >
                  {busy === a.key ? "Dismissing…" : "Dismiss"}
                </Button>
              </div>
            </GlassPanel>
          </li>
        ))}
      </ul>
    </section>
  );
}
