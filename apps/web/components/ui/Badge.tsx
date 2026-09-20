"use client";

import { useId, useState } from "react";
import { cn } from "@/lib/cn";
import type { Badge as BadgeData } from "@/lib/types";

const TONE: Record<string, string> = {
  alert: "border-[var(--critical)] text-[var(--critical)] bg-[var(--glass-strong)]",
  warn: "border-[var(--caution)] text-[var(--caution)] bg-[var(--glass-strong)]",
  info: "border-[var(--primary)] text-[var(--primary)] bg-[var(--primary-soft)]",
  muted: "border-[var(--border-strong)] text-[var(--fg-muted)] bg-[var(--glass)]",
};

/** Every tone also carries a glyph, so tone is never the only signal. */
const GLYPH: Record<string, string> = {
  alert: "▲",
  warn: "●",
  info: "◆",
  muted: "○",
};

export function Pill({
  tone = "muted",
  className,
  children,
}: {
  tone?: keyof typeof TONE;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5",
        "text-xs font-medium tracking-wide",
        TONE[tone] ?? TONE.muted,
        className,
      )}
    >
      <span aria-hidden="true" className="text-[0.6rem] leading-none">
        {GLYPH[tone] ?? GLYPH.muted}
      </span>
      {children}
    </span>
  );
}

/**
 * A radar badge whose rule is readable, not just hoverable.
 *
 * DESIGN.md 10.1 asks for rule-citing tooltips. A hover-only tooltip is
 * unreachable by keyboard and invisible to touch, so this is a button that
 * toggles a described region, and the description is real text in the DOM.
 */
export function RuleBadge({ badge }: { badge: BadgeData }) {
  const [open, setOpen] = useState(false);
  const id = useId();

  return (
    <span className="relative inline-block">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5",
          "text-xs font-medium tracking-wide cursor-pointer",
          "hover:brightness-105",
          TONE[badge.tone] ?? TONE.muted,
        )}
      >
        <span aria-hidden="true" className="text-[0.6rem] leading-none">
          {GLYPH[badge.tone] ?? GLYPH.muted}
        </span>
        {badge.label}
        <span className="sr-only">. Why this is flagged:</span>
      </button>
      <span
        id={id}
        role="note"
        hidden={!open}
        className={cn(
          "absolute left-0 top-full z-20 mt-1.5 w-64 rounded-[var(--radius-sm)] border p-2.5",
          "border-[var(--glass-border)] bg-[var(--surface)] shadow-[var(--glass-shadow)]",
          "text-xs leading-relaxed text-[var(--fg-muted)]",
        )}
      >
        {badge.tooltip}
      </span>
    </span>
  );
}
