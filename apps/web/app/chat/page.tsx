"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { GlassPanel, SectionHeading } from "@/components/ui/Glass";
import { Button } from "@/components/ui/Button";
import { ErrorPanel } from "@/components/ui/States";
import { AnswerText, type Citation } from "@/components/chat/AnswerText";
import { API_BASE } from "@/lib/api";
import { streamSse } from "@/lib/sse";

type Turn = {
  question: string;
  text: string;
  citations: Citation[];
  tool: string | null;
  toolsUsed: string[];
  error: string | null;
  declined: boolean;
  done: boolean;
};

/** The four PS questions (DESIGN.md §13, rows 11a–11d). */
const SUGGESTIONS = [
  "Where did I spend the most last month?",
  "How much of my budget is already committed?",
  "Which subscriptions am I paying for without realising?",
  "Can I afford a ₹40,000 phone this month?",
];

/** Affordability questions get a card deep-linked to the simulator (T11). */
const AFFORDABILITY = /\b(can i afford|should i buy|afford(?:able)?|if i (?:cancel|cut|stop))\b/i;

function emptyTurn(question: string): Turn {
  return {
    question,
    text: "",
    citations: [],
    tool: null,
    toolsUsed: [],
    error: null,
    declined: false,
    done: false,
  };
}

export default function ChatPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const liveRef = useRef<HTMLDivElement>(null);

  // Focus returns to the input after each answer so the keyboard path loops
  // without reaching for the mouse.
  useEffect(() => {
    if (!busy) inputRef.current?.focus();
  }, [busy]);

  async function ask(question: string) {
    const trimmed = question.trim();
    if (!trimmed || busy) return;

    setDraft("");
    setBusy(true);
    const index = turns.length;
    setTurns((prev) => [...prev, emptyTurn(trimmed)]);

    const patch = (fn: (t: Turn) => Turn) =>
      setTurns((prev) => prev.map((t, i) => (i === index ? fn(t) : t)));

    try {
      for await (const frame of streamSse(API_BASE + "/api/agent/ask", {
        method: "POST",
        body: JSON.stringify({ question: trimmed }),
      })) {
        const data = frame.data as Record<string, unknown>;
        if (frame.event === "tool") {
          patch((t) => ({
            ...t,
            tool: String(data.label ?? data.name ?? ""),
            toolsUsed: [...t.toolsUsed, String(data.name ?? "")],
          }));
        } else if (frame.event === "text") {
          patch((t) => ({
            ...t,
            text: String(data.text ?? ""),
            declined: Boolean(data.declined),
            tool: null,
          }));
        } else if (frame.event === "error") {
          patch((t) => ({ ...t, error: String(data.message ?? "Something went wrong."), tool: null }));
        } else if (frame.event === "done") {
          patch((t) => ({
            ...t,
            citations: (data.citations as Citation[]) ?? [],
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
    }
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <SectionHeading>Ask about your money</SectionHeading>
        <p className="max-w-2xl text-sm text-[var(--fg-muted)]">
          Every figure below is computed by the engine, not written by the model.
          Click any underlined amount to see the exact transactions behind it.
        </p>
      </header>

      {turns.length === 0 && (
        <GlassPanel>
          <h2 className="mb-3 text-sm font-semibold">Try one of these</h2>
          <ul className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((q) => (
              <li key={q}>
                <Button variant="ghost" onClick={() => ask(q)} disabled={busy}>
                  {q}
                </Button>
              </li>
            ))}
          </ul>
        </GlassPanel>
      )}

      <div
        ref={liveRef}
        aria-live="polite"
        aria-busy={busy}
        aria-label="Conversation"
        className="space-y-5"
      >
        {turns.map((turn, i) => (
          <article key={i} className="space-y-3">
            <h2 className="text-sm font-semibold text-[var(--fg-muted)]">
              <span className="sr-only">You asked: </span>
              {turn.question}
            </h2>

            <GlassPanel>
              {turn.tool && (
                <p className="flex items-center gap-2 text-sm text-[var(--fg-muted)]">
                  <span aria-hidden="true" className="animate-pulse">
                    ◍
                  </span>
                  {turn.tool}…
                </p>
              )}

              {turn.error && <ErrorPanel message={turn.error} />}

              {turn.text && (
                <>
                  {turn.declined && (
                    <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--caution)]">
                      Outside what FinPilot does
                    </p>
                  )}
                  <AnswerText text={turn.text} citations={turn.citations} />
                </>
              )}

              {!turn.text && !turn.error && !turn.tool && (
                <p className="text-sm text-[var(--fg-muted)]">Thinking…</p>
              )}

              {turn.done && turn.toolsUsed.length > 0 && (
                <p className="mt-3 border-t border-[var(--border)] pt-2 text-xs text-[var(--fg-muted)]">
                  Answered using{" "}
                  {Array.from(new Set(turn.toolsUsed)).join(", ").replace(/_/g, " ")}.
                </p>
              )}
            </GlassPanel>

            {turn.done && AFFORDABILITY.test(turn.question) && (
              <GlassPanel>
                <h3 className="text-sm font-semibold">Try it in the simulator</h3>
                <p className="mt-1 text-sm text-[var(--fg-muted)]">
                  Model the purchase against your goals, and see which ETAs move.
                </p>
                <p className="mt-3">
                  <Link
                    href="/goals"
                    className="underline decoration-dotted underline-offset-4 hover:decoration-solid"
                  >
                    Open the What-If simulator
                  </Link>
                </p>
              </GlassPanel>
            )}
          </article>
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void ask(draft);
        }}
        className="flex gap-2"
      >
        <label htmlFor="chat-input" className="sr-only">
          Ask a question about your money
        </label>
        <input
          id="chat-input"
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={busy}
          autoComplete="off"
          placeholder="Where did I spend the most last month?"
          className="flex-1 rounded-md border border-[var(--border)] bg-[var(--glass)] px-3 py-2 text-sm
                     focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2
                     focus-visible:outline-[var(--accent)]"
        />
        <Button type="submit" disabled={busy || !draft.trim()}>
          {busy ? "Asking…" : "Ask"}
        </Button>
      </form>
    </div>
  );
}
