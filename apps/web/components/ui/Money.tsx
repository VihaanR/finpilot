import { cn } from "@/lib/cn";
import { formatPaise, rupeesInWords } from "@/lib/format";

/**
 * The only place paise become rupees.
 *
 * Sighted readers get the grouped glyph; screen readers get the magnitude in
 * words, because "₹18,400" is routinely announced as a digit string and the
 * magnitude is the one thing that must not be misheard (DESIGN.md 11).
 *
 * `signed` renders an explicit + or -. Direction is never carried by colour
 * alone, so the sign stays even when the colour says the same thing.
 */
export function Money({
  paise,
  className,
  exact = false,
  signed = false,
  tone,
}: {
  paise: number;
  className?: string;
  exact?: boolean;
  signed?: boolean;
  tone?: "positive" | "critical" | "muted";
}) {
  const magnitude = signed ? Math.abs(paise) : paise;
  const prefix = signed ? (paise < 0 ? "−" : "+") : "";
  const spokenPrefix = signed ? (paise < 0 ? "minus " : "plus ") : "";

  return (
    <span
      className={cn(
        "tnum",
        tone === "positive" && "text-[var(--positive)]",
        tone === "critical" && "text-[var(--critical)]",
        tone === "muted" && "text-[var(--fg-muted)]",
        className,
      )}
    >
      <span aria-hidden="true">
        {prefix}
        {formatPaise(magnitude, { paise: exact })}
      </span>
      <span className="sr-only">
        {spokenPrefix}
        {rupeesInWords(magnitude)}
      </span>
    </span>
  );
}
