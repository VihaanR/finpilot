"use client";

import { useRef, useState } from "react";
import { GlassPanel, SectionHeading } from "@/components/ui/Glass";
import { Button } from "@/components/ui/Button";
import { AnswerText, type Citation } from "@/components/chat/AnswerText";
import { ActionCard, type ActionStatus } from "@/components/agent/ActionCard";
import { API_BASE, api } from "@/lib/api";
import { streamSse } from "@/lib/sse";
import type { ApplyResponse, ProposedAction } from "@/lib/types";

/**
 * The agentic surface: say what you want done, in one sentence, and the agent
 * works out the steps.
 *
 * It streams from `/api/agent/act`, which is a different endpoint from the
 * `/chat` page's `/api/agent/ask` — deliberately. Only this one can stage
 * changes, so the read-only chat surface cannot offer to delete anything, and
 * the eval goldens that run through `/ask` keep their exact behaviour.
 *
 * Nothing here writes. The agent stages; the user approves; the write happens
 * in one deterministic call to `/api/agent/actions/apply`.
 */

const EXAMPLES = [
  "Set up a goal to buy a car for 50L by March 2031",
  "Find the duplicated charge this month and remove it",
  "Start a 5 lakh emergency fund and remove any duplicate transactions",
];

type Turn = {
  question: string;
  text: string;
  tool: string | null;
  citations: Citation[];
  actions: ProposedAction[];
  statuses: Record<string, ActionStatus>;
  errors: Record<string, string>;
  error: string | null;
  done: boolean;
};

function emptyTurn(question: string): Turn {
  return {
    question,
    text: "",
    tool: null,
    citations: [],
    actions: [],
    statuses: {},
    errors: {},
    error: null,
    done: false,
  };
}

export function AgentPanel({ onApplied }: { onApplied?: () => void }) {
  const [draft, setDraft] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const patchAt = (index: number, fn: (t: Turn) => Turn) =>
    setTurns((prev) => prev.map((t, i) => (i === index ? fn(t) : t)));

  async function send(question: string) {
    const trimmed = question.trim();
    if (!trimmed || busy) return;

    setDraft("");
    setBusy(true);
    const index = turns.length;
    setTurns((prev) => [...prev, emptyTurn(trimmed)]);
    const patch = (fn: (t: Turn) => Turn) => patchAt(index, fn);

    try {
      for await (const frame of streamSse(API_BASE + "/api/agent/act", {
        method: "POST",
        body: JSON.stringify({ question: trimmed }),
      })) {
        const data = frame.data as Record<string, unknown>;
        if (frame.event === "tool") {
          patch((t) => ({ ...t, tool: String(data.label ?? data.name ?? "") }));
        } else if (frame.event === "text") {
          patch((t) => ({ ...t, text: String(data.text ?? ""), tool: null }));
        } else if (frame.event === "error") {
          patch((t) => ({
            ...t,
            error: String(data.message ?? "Something went wrong."),
            tool: null,
          }));
        } else if (frame.event === "done") {
          const actions = (data.actions as ProposedAction[]) ?? [];
          patch((t) => ({
            ...t,
            citations: (data.citations as Citation[]) ?? [],
            actions,
            statuses: Object.fromEntries(
              actions.map((a) => [a.id, "pending" as ActionStatus]),
            ),
            tool: null,
            done: true,
          }));
        }
      }
    } catch (e) {
      patch((t) => ({ ...t, error: (e as Error).message, tool: null, done: true }));
    } finally {
      patch((t) => ({ ...t, done: true }));
      setBusy(false);
      inputRef.current?.focus();
    }
  }

  async function apply(index: number, actions: ProposedAction[]) {
    if (actions.length === 0) return;
    patchAt(index, (t) => ({
      ...t,
      statuses: {
        ...t.statuses,
        ...Object.fromEntries(actions.map((a) => [a.id, "applying" as ActionStatus])),
      },
    }));

    try {
      const res = await api.post<ApplyResponse>("/api/agent/actions/apply", {
        actions: actions.map((a) => ({ id: a.id, kind: a.kind, params: a.params })),
      });
      patchAt(index, (t) => {
        const statuses = { ...t.statuses };
        const errors = { ...t.errors };
        for (const r of res.results) {
          statuses[r.id] = r.ok ? "applied" : "failed";
          if (!r.ok && r.error) errors[r.id] = r.error;
        }
        return { ...t, statuses, errors };
      });
      if (res.applied > 0) onApplied?.();
    } catch (e) {
      patchAt(index, (t) => ({
        ...t,
        statuses: {
          ...t.statuses,
          ...Object.fromEntries(actions.map((a) => [a.id, "failed" as ActionStatus])),
        },
        errors: {
          ...t.errors,
          ...Object.fromEntries(actions.map((a) => [a.id, (e as Error).message])),
        },
      }));
    }
  }

  return (
    <GlassPanel strong className="p-6">
      <SectionHeading hint="Staged for your approval">Tell FinPilot what to do</SectionHeading>
      <p className="max-w-2xl text-sm text-[var(--fg-muted)]">
        Describe what you want in a sentence — set up a goal, clear out a
        duplicate. Nothing changes until you approve it.
      </p>

      <form
        className="mt-4 flex flex-col gap-2 sm:flex-row"
        onSubmit={(e) => {
          e.preventDefault();
          void send(draft);
        }}
      >
        <label htmlFor="agent-input" className="sr-only">
          What would you like FinPilot to do?
        </label>
        <textarea
          id="agent-input"
          ref={inputRef}
          rows={2}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send(draft);
            }
          }}
          placeholder="Set up a goal to buy a car for 50L, and remove that duplicated charge"
          className="min-h-[3.5rem] flex-1 rounded-xl border border-[var(--border-strong)] bg-[var(--surface)] px-4 py-3 text-[var(--fg)] placeholder:text-[var(--fg-subtle)]"
        />
        <Button type="submit" disabled={busy || !draft.trim()}>
          {busy ? "Working…" : "Go"}
        </Button>
      </form>

      {turns.length === 0 ? (
        <ul className="mt-3 flex flex-wrap gap-2">
          {EXAMPLES.map((q) => (
            <li key={q}>
              <button
                type="button"
                onClick={() => void send(q)}
                disabled={busy}
                className="rounded-full border border-[var(--border-strong)] px-3 py-1.5 text-sm text-[var(--fg-muted)] hover:bg-[var(--primary-soft)] disabled:opacity-50"
              >
                {q}
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <div
        role="log"
        aria-live="polite"
        aria-busy={busy}
        aria-label="Agent activity"
        className="mt-4 space-y-5 empty:mt-0"
      >
        {turns.map((turn, i) => {
          const pending = turn.actions.filter((a) => turn.statuses[a.id] === "pending");
          return (
            <article key={i} className="space-y-3 border-t border-[var(--border)] pt-4">
              <p className="text-sm font-medium text-[var(--fg)]">{turn.question}</p>

              {turn.tool ? (
                <p className="text-sm text-[var(--fg-muted)]">
                  <span aria-hidden="true">◍ </span>
                  {turn.tool}…
                </p>
              ) : null}

              {turn.text ? (
                <div className="text-[var(--fg-muted)]">
                  <AnswerText text={turn.text} citations={turn.citations} />
                </div>
              ) : null}

              {turn.error ? (
                <p className="text-sm text-[var(--critical)]">{turn.error}</p>
              ) : null}

              {turn.actions.length > 0 ? (
                <>
                  <ul className="space-y-2">
                    {turn.actions.map((a) => (
                      <ActionCard
                        key={a.id}
                        action={a}
                        status={turn.statuses[a.id] ?? "pending"}
                        error={turn.errors[a.id]}
                        onApply={() => void apply(i, [a])}
                        onSkip={() =>
                          patchAt(i, (t) => ({
                            ...t,
                            statuses: { ...t.statuses, [a.id]: "skipped" },
                          }))
                        }
                      />
                    ))}
                  </ul>
                  {pending.length > 1 ? (
                    <Button size="sm" onClick={() => void apply(i, pending)}>
                      Apply all ({pending.length})
                    </Button>
                  ) : null}
                </>
              ) : null}

              {turn.done && turn.actions.length === 0 && !turn.error && turn.text ? (
                <p className="text-xs text-[var(--fg-subtle)]">
                  Nothing staged — this was answered, not changed.
                </p>
              ) : null}
            </article>
          );
        })}
      </div>
    </GlassPanel>
  );
}
