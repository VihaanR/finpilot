"use client";

import { GlassPanel, SectionHeading } from "@/components/ui/Glass";
import { Money } from "@/components/ui/Money";
import { useApi } from "@/lib/useApi";

interface GuardEvent {
  id: string;
  created_at: string;
  site: string;
  outcome: "wait" | "continue" | "dismiss";
  cart_paise: number;
}

interface GuardEvents {
  events: GuardEvent[];
  count: number;
  stopped_count: number;
  avoided_paise: number;
}

const OUTCOME_LABEL: Record<GuardEvent["outcome"], string> = {
  wait: "waited",
  dismiss: "backed out",
  continue: "went ahead",
};

/**
 * What the browser extension stopped, on the dashboard.
 *
 * Renders nothing until the extension has actually reported something, so a
 * fresh demo isn't cluttered by an empty panel explaining a feature the
 * viewer hasn't seen yet.
 */
export function GuardCard() {
  const { data } = useApi<GuardEvents>("/api/guard/events?limit=5");
  if (!data || data.count === 0) return null;

  return (
    <GlassPanel className="p-6">
      <SectionHeading hint="From the browser extension">Budget Guard</SectionHeading>
      <p className="text-sm text-[var(--fg-muted)]">
        {data.stopped_count > 0 ? (
          <>
            You stepped away from{" "}
            <Money paise={data.avoided_paise} className="font-medium" /> across{" "}
            {data.stopped_count} checkout{data.stopped_count === 1 ? "" : "s"}.
          </>
        ) : (
          <>Budget Guard flagged {data.count} checkout{data.count === 1 ? "" : "s"}.</>
        )}
      </p>
      <ul className="mt-3 space-y-2">
        {data.events.map((e) => (
          <li key={e.id} className="flex items-baseline justify-between gap-3 text-sm">
            <span className="text-[var(--fg-muted)]">
              {e.site} · {OUTCOME_LABEL[e.outcome] ?? e.outcome}
            </span>
            <Money paise={e.cart_paise} className="tnum" />
          </li>
        ))}
      </ul>
    </GlassPanel>
  );
}
