"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { formatDate, titleCase } from "@/lib/format";
import type { Transaction } from "@/lib/types";
import { Money } from "@/components/ui/Money";
import { Button } from "@/components/ui/Button";
import type { DrawerRequest } from "./CitationContext";

const FOCUSABLE =
  'a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])';

export function TransactionDrawer({
  request,
  onClose,
}: {
  request: DrawerRequest | null;
  onClose: () => void;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const returnFocusTo = useRef<HTMLElement | null>(null);
  const [rows, setRows] = useState<Transaction[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const open = request !== null;

  useEffect(() => {
    if (!open) return;
    returnFocusTo.current = document.activeElement as HTMLElement | null;
    setRows(null);
    setError(null);

    let cancelled = false;
    const ids = request.txnIds.join(",");
    api
      .get<{ transactions: Transaction[] }>(
        `/api/transactions?limit=1000&ids=${encodeURIComponent(ids)}`,
      )
      .then((data) => {
        if (!cancelled) setRows(data.transactions);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });

    return () => {
      cancelled = true;
    };
  }, [open, request]);

  // Move focus in when it opens, and back to the trigger when it closes.
  useEffect(() => {
    if (open) {
      panelRef.current?.focus();
    } else {
      returnFocusTo.current?.focus();
      returnFocusTo.current = null;
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;

      const panel = panelRef.current;
      if (!panel) return;
      const items = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (!items.length) {
        event.preventDefault();
        panel.focus();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;

      if (event.shiftKey && (active === first || active === panel)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const total = rows?.reduce(
    (sum, r) => sum + (r.direction === "CREDIT" ? r.amount_paise : -r.amount_paise),
    0,
  );

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div
        className="absolute inset-0 bg-[color-mix(in_srgb,var(--bg)_70%,transparent)] backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={`Transactions behind ${request.title}`}
        tabIndex={-1}
        className="relative flex h-full w-full max-w-xl flex-col border-l border-[var(--glass-border)] bg-[var(--surface)] shadow-[var(--glass-shadow)]"
      >
        <header className="flex items-start justify-between gap-4 border-b border-[var(--border)] px-5 py-4">
          <div>
            <h2 className="font-[family-name:var(--font-display)] text-lg text-[var(--fg)]">
              {request.title}
            </h2>
            <p className="mt-0.5 text-sm text-[var(--fg-muted)]">
              {request.subtitle ??
                `${request.txnIds.length} transaction${request.txnIds.length === 1 ? "" : "s"} behind this figure`}
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Close
            <span aria-hidden="true">✕</span>
          </Button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {error ? (
            <p role="alert" className="text-sm text-[var(--critical)]">
              {error}
            </p>
          ) : rows === null ? (
            <p className="text-sm text-[var(--fg-muted)]" aria-live="polite">
              Loading transactions…
            </p>
          ) : rows.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">
              No transactions matched this citation.
            </p>
          ) : (
            <table className="w-full border-collapse text-sm">
              <caption className="sr-only">
                Transactions that make up {request.title}
              </caption>
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs uppercase tracking-wider text-[var(--fg-subtle)]">
                  <th scope="col" className="py-2 pr-3 font-medium">Date</th>
                  <th scope="col" className="py-2 pr-3 font-medium">Merchant</th>
                  <th scope="col" className="py-2 pr-3 font-medium">Category</th>
                  <th scope="col" className="py-2 text-right font-medium">Amount</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className="border-b border-[var(--border)] align-top">
                    <td className="py-2 pr-3 whitespace-nowrap text-[var(--fg-muted)]">
                      {formatDate(row.txn_date)}
                    </td>
                    <td className="py-2 pr-3">
                      <span className="block text-[var(--fg)]">{row.normalized_merchant}</span>
                      <span className="block text-xs text-[var(--fg-subtle)]">
                        {row.raw_narration}
                      </span>
                    </td>
                    <td className="py-2 pr-3 text-[var(--fg-muted)]">
                      {titleCase(row.category_slug)}
                    </td>
                    <td className="py-2 text-right">
                      <Money
                        paise={row.direction === "CREDIT" ? row.amount_paise : -row.amount_paise}
                        signed
                        exact
                        tone={row.direction === "CREDIT" ? "positive" : undefined}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {rows && rows.length > 0 ? (
          <footer className="border-t border-[var(--border)] px-5 py-3 text-sm">
            <span className="text-[var(--fg-muted)]">Net of these rows: </span>
            <Money paise={total ?? 0} signed exact className="font-medium" />
          </footer>
        ) : null}
      </div>
    </div>
  );
}
