"use client";

import { Button } from "@/components/ui/Button";
import { CitationChip } from "@/components/citations/CitationChip";
import type { ProposedAction } from "@/lib/types";

export type ActionStatus = "pending" | "applying" | "applied" | "skipped" | "failed";

/**
 * One staged change, with the figures it would write.
 *
 * The amount lives here rather than in the agent's prose on purpose. It came
 * from the user's own sentence, not from a tool, so it has no citation to
 * attach — and an uncited figure in the answer text is exactly what the
 * citation audit is built to flag. Rendering it as structured data keeps the
 * "every figure in prose is traceable" contract intact.
 */
export function ActionCard({
  action,
  status,
  error,
  onApply,
  onSkip,
}: {
  action: ProposedAction;
  status: ActionStatus;
  error?: string;
  onApply: () => void;
  onSkip: () => void;
}) {
  const settled = status === "applied" || status === "skipped";

  return (
    <li className="rounded-xl border border-[var(--border-strong)] bg-[var(--surface)] p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <p className="font-medium text-[var(--fg)]">
          {/* Never colour alone: the word "Deletes" carries the warning too. */}
          {action.destructive ? (
            <span className="mr-2 rounded-full bg-[var(--critical-soft,var(--border-strong))] px-2 py-0.5 text-xs font-semibold uppercase tracking-wide text-[var(--critical)]">
              ⚠ Deletes
            </span>
          ) : null}
          {action.title}
        </p>
        <StatusPill status={status} />
      </div>

      <p className="tnum mt-1 text-sm text-[var(--fg-muted)]">{action.detail}</p>

      {action.txn_ids.length > 0 ? (
        <p className="mt-2 text-sm">
          <CitationChip
            txnIds={action.txn_ids}
            title={action.title}
            subtitle="The transaction this would remove"
          >
            <span>See the transaction</span>
          </CitationChip>
        </p>
      ) : null}

      {error ? (
        <p className="mt-2 text-sm text-[var(--critical)]">{error}</p>
      ) : null}

      {!settled ? (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            size="sm"
            variant={action.destructive ? "danger" : "primary"}
            onClick={onApply}
            disabled={status === "applying"}
          >
            {status === "applying" ? "Applying…" : "Apply"}
          </Button>
          <Button size="sm" variant="ghost" onClick={onSkip} disabled={status === "applying"}>
            Skip
          </Button>
        </div>
      ) : null}
    </li>
  );
}

function StatusPill({ status }: { status: ActionStatus }) {
  if (status === "pending" || status === "applying") return null;
  const label =
    status === "applied" ? "✓ Applied" : status === "skipped" ? "Skipped" : "✕ Failed";
  const tone =
    status === "applied"
      ? "text-[var(--positive)]"
      : status === "failed"
        ? "text-[var(--critical)]"
        : "text-[var(--fg-subtle)]";
  return <span className={`text-xs font-medium ${tone}`}>{label}</span>;
}
