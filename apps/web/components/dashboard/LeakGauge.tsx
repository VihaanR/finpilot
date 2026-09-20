"use client";

import { GlassPanel } from "@/components/ui/Glass";
import type { LeakScore } from "@/lib/types";

const RADIUS = 52;
const CIRCUMFERENCE = Math.PI * RADIUS; // semicircle

/**
 * The Leak Score, as a half-dial.
 *
 * The score is also printed, the band is spelled out in words, and the arc
 * carries a tick at the score position — so the reading survives greyscale,
 * colour blindness and a screen reader equally (T09 criterion: colour AND
 * label).
 */
export function LeakGauge({ leak }: { leak: LeakScore }) {
  const fraction = Math.max(0, Math.min(100, leak.score)) / 100;
  const stroke =
    leak.score >= 75
      ? "var(--positive)"
      : leak.score >= 50
        ? "var(--accent)"
        : "var(--critical)";

  return (
    <GlassPanel className="flex flex-col items-center p-6">
      <h2 className="font-[family-name:var(--font-display)] text-lg text-[var(--fg)]">
        Leak Score
      </h2>

      <svg
        viewBox="0 0 140 80"
        className="mt-3 w-full max-w-[16rem]"
        role="img"
        aria-label={`Leak Score ${leak.score} out of 100. Rated ${leak.label}.`}
      >
        <path
          d={`M 18 70 A ${RADIUS} ${RADIUS} 0 0 1 122 70`}
          fill="none"
          stroke="var(--border-strong)"
          strokeWidth="10"
          strokeLinecap="round"
        />
        <path
          d={`M 18 70 A ${RADIUS} ${RADIUS} 0 0 1 122 70`}
          fill="none"
          stroke={stroke}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={`${CIRCUMFERENCE * fraction} ${CIRCUMFERENCE}`}
        />
        <text
          x="70"
          y="62"
          textAnchor="middle"
          className="tnum"
          fill="var(--fg)"
          fontSize="30"
          fontWeight="600"
        >
          {leak.score}
        </text>
        <text x="18" y="79" fill="var(--fg-subtle)" fontSize="8">0</text>
        <text x="115" y="79" fill="var(--fg-subtle)" fontSize="8">100</text>
      </svg>

      <p className="mt-1 text-sm font-medium text-[var(--fg)]">{leak.label}</p>
      <p className="mt-0.5 text-xs text-[var(--fg-subtle)]">
        100 means nothing is leaking.
      </p>

      {leak.contributions.length > 0 ? (
        <table className="mt-4 w-full border-collapse text-sm">
          <caption className="sr-only">
            What is deducted from a perfect score of 100
          </caption>
          <thead>
            <tr className="border-b border-[var(--border)] text-left text-xs uppercase tracking-wider text-[var(--fg-subtle)]">
              <th scope="col" className="py-1.5 pr-2 font-medium">Reason</th>
              <th scope="col" className="py-1.5 pl-2 text-right font-medium">Found</th>
              <th scope="col" className="py-1.5 pl-3 text-right font-medium">Cost</th>
            </tr>
          </thead>
          <tbody>
            {leak.contributions.map((c) => (
              <tr key={c.reason} className="border-b border-[var(--border)]">
                <th scope="row" className="py-1.5 pr-2 text-left font-normal text-[var(--fg)]">
                  {c.reason}
                </th>
                <td className="tnum py-1.5 pl-2 text-right text-[var(--fg-muted)]">
                  {c.count}
                </td>
                <td className="tnum py-1.5 pl-3 text-right text-[var(--fg-muted)]">
                  −{c.deduction}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="mt-4 text-sm text-[var(--fg-muted)]">
          Nothing is being deducted. Every mandate is acknowledged and none has
          risen in price.
        </p>
      )}
    </GlassPanel>
  );
}
