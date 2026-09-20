"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import type { RevokeKit as RevokeKitData } from "@/lib/types";

export function RevokeKit({
  kit,
  merchant,
}: {
  kit: RevokeKitData;
  merchant: string;
}) {
  const [copied, setCopied] = useState("");

  async function copy(text: string, what: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(`${what} copied to your clipboard.`);
    } catch {
      setCopied("Could not reach the clipboard. Select the text and copy it.");
    }
  }

  return (
    <div className="mt-3 rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--primary-soft)] p-4">
      <h4 className="text-sm font-medium text-[var(--fg)]">
        How to stop {merchant}
      </h4>
      <p className="mt-0.5 text-xs text-[var(--fg-subtle)]">
        Mandate rail: {kit.channel.replace(/_/g, " ").toLowerCase()}
      </p>

      <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-[var(--fg-muted)]">
        {kit.steps.map((step, i) => (
          <li key={i}>{step}</li>
        ))}
      </ol>

      <details className="mt-3">
        <summary className="cursor-pointer text-sm text-[var(--fg)]">
          Email template
        </summary>
        <pre className="mt-2 max-h-56 overflow-auto whitespace-pre-wrap rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface)] p-3 text-xs text-[var(--fg-muted)]">
          {kit.email_template}
        </pre>
      </details>

      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" onClick={() => copy(kit.steps.join("\n"), "The steps")}>
          Copy steps
        </Button>
        <Button
          size="sm"
          onClick={() => copy(kit.email_template, "The email")}
        >
          Copy email
        </Button>
      </div>

      <p aria-live="polite" className="mt-2 text-xs text-[var(--fg-muted)]">
        {copied}
      </p>
    </div>
  );
}
