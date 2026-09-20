"use client";

import { cn } from "@/lib/cn";
import { Money } from "@/components/ui/Money";
import { useCitations } from "./CitationContext";

/**
 * A figure you can open.
 *
 * The underline is deliberate: the affordance must not be colour alone, and a
 * dotted underline reads as "there is more here" without shouting.
 */
export function CitationChip({
  paise,
  txnIds,
  title,
  subtitle,
  className,
  exact,
  children,
}: {
  paise?: number;
  txnIds: string[];
  title: string;
  subtitle?: string;
  className?: string;
  exact?: boolean;
  children?: React.ReactNode;
}) {
  const { open } = useCitations();
  const count = txnIds.length;

  return (
    <button
      type="button"
      onClick={() => open({ title, txnIds, subtitle })}
      className={cn(
        "inline-flex items-baseline gap-1 rounded-sm underline decoration-dotted",
        "decoration-[var(--accent)] underline-offset-4",
        "hover:decoration-solid hover:text-[var(--accent)] cursor-pointer",
        className,
      )}
    >
      {children ?? (paise !== undefined ? <Money paise={paise} exact={exact} /> : null)}
      <span className="sr-only">
        . Show the {count} transaction{count === 1 ? "" : "s"} behind this figure.
      </span>
      <span aria-hidden="true" className="text-[0.65em] text-[var(--accent)]">
        ⌕
      </span>
    </button>
  );
}
