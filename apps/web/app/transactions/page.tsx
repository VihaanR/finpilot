"use client";

import { useEffect, useMemo, useState } from "react";
import { GlassPanel, SectionHeading } from "@/components/ui/Glass";
import { Button } from "@/components/ui/Button";
import { Money } from "@/components/ui/Money";
import { Pill } from "@/components/ui/Badge";
import { ErrorPanel, LoadingPanel, EmptyPanel } from "@/components/ui/States";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { formatDate, titleCase } from "@/lib/format";
import type { Category, Transaction } from "@/lib/types";

const PAGE_SIZE = 50;

export default function TransactionsPage() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [page, setPage] = useState(0);
  const [debounced, setDebounced] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const t = setTimeout(() => {
      setDebounced(search);
      setPage(0);
    }, 250);
    return () => clearTimeout(t);
  }, [search]);

  const path = useMemo(() => {
    const params = new URLSearchParams({
      limit: String(PAGE_SIZE),
      offset: String(page * PAGE_SIZE),
    });
    if (debounced) params.set("search", debounced);
    if (category) params.set("category", category);
    return `/api/transactions?${params}`;
  }, [debounced, category, page]);

  const { data, error, loading, reload } = useApi<{
    transactions: Transaction[];
    total: number;
  }>(path);
  const { data: cats } = useApi<{ categories: Category[] }>("/api/categories");

  async function override(txn: Transaction, slug: string) {
    if (!slug || slug === txn.category_slug) return;
    try {
      const r = await api.patch<{ message: string }>(
        `/api/transactions/${txn.id}/category`,
        { category_slug: slug },
      );
      setNotice(r.message);
      reload();
    } catch (e) {
      setNotice((e as Error).message);
    }
  }

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6">
      <div>
        <SectionHeading as="h1" hint={data ? `${data.total} in total` : undefined}>
          Transactions
        </SectionHeading>
        <p className="max-w-2xl text-[var(--fg-muted)]">
          Correcting a category here teaches the rule. Every past transaction
          from the same merchant is updated with it.
        </p>
      </div>

      <GlassPanel className="p-5">
        <div className="grid gap-4 sm:grid-cols-[1fr_16rem]">
          <div>
            <label htmlFor="q" className="block text-sm font-medium text-[var(--fg)]">
              Search merchant or narration
            </label>
            <input
              id="q"
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="SWIGGY, rent, NEFT…"
              className="mt-1 w-full rounded-[var(--radius-sm)] border border-[var(--border-strong)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--fg)]"
            />
          </div>
          <div>
            <label htmlFor="cat" className="block text-sm font-medium text-[var(--fg)]">
              Category
            </label>
            <select
              id="cat"
              value={category}
              onChange={(e) => {
                setCategory(e.target.value);
                setPage(0);
              }}
              className="mt-1 w-full rounded-[var(--radius-sm)] border border-[var(--border-strong)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--fg)]"
            >
              <option value="">All categories</option>
              {cats?.categories.map((c) => (
                <option key={c.slug} value={c.slug}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </GlassPanel>

      <p aria-live="polite" className="text-sm text-[var(--positive)]">
        {notice}
      </p>

      {error ? <ErrorPanel message={error} /> : null}
      {loading && !data ? <LoadingPanel label="Loading transactions…" /> : null}

      {data && data.transactions.length === 0 ? (
        <EmptyPanel title="No transactions match">
          {debounced || category
            ? "Try a different search or category."
            : undefined}
        </EmptyPanel>
      ) : null}

      {data && data.transactions.length > 0 ? (
        <GlassPanel className="overflow-x-auto p-5">
          <table className="w-full border-collapse text-sm">
            <caption className="sr-only">
              Your transactions, most recent first
            </caption>
            <thead>
              <tr className="border-b border-[var(--border)] text-left text-xs uppercase tracking-wider text-[var(--fg-subtle)]">
                <th scope="col" className="py-2 pr-3 font-medium">Date</th>
                <th scope="col" className="py-2 pr-3 font-medium">Merchant</th>
                <th scope="col" className="py-2 pr-3 font-medium">Category</th>
                <th scope="col" className="py-2 pr-3 font-medium">Channel</th>
                <th scope="col" className="py-2 text-right font-medium">Amount</th>
              </tr>
            </thead>
            <tbody>
              {data.transactions.map((t) => (
                <tr key={t.id} className="border-b border-[var(--border)] align-top">
                  <td className="py-2.5 pr-3 whitespace-nowrap text-[var(--fg-muted)]">
                    {formatDate(t.txn_date)}
                  </td>
                  <th scope="row" className="py-2.5 pr-3 text-left font-normal">
                    <span className="block text-[var(--fg)]">
                      {t.normalized_merchant}
                    </span>
                    <span className="block max-w-xs truncate text-xs text-[var(--fg-subtle)]">
                      {t.raw_narration}
                    </span>
                  </th>
                  <td className="py-2.5 pr-3">
                    <label className="sr-only" htmlFor={`cat-${t.id}`}>
                      Category for {t.normalized_merchant} on {formatDate(t.txn_date)}
                    </label>
                    <select
                      id={`cat-${t.id}`}
                      value={t.category_slug}
                      onChange={(e) => override(t, e.target.value)}
                      className="max-w-[11rem] rounded-[var(--radius-sm)] border border-[var(--border)] bg-transparent px-2 py-1 text-xs text-[var(--fg)]"
                    >
                      {cats?.categories.map((c) => (
                        <option key={c.slug} value={c.slug}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                    {t.category_source === "USER" ? (
                      <span className="mt-1 block">
                        <Pill tone="info">Your rule</Pill>
                      </span>
                    ) : null}
                  </td>
                  <td className="py-2.5 pr-3 text-xs text-[var(--fg-muted)]">
                    {titleCase(t.channel)}
                  </td>
                  <td className="py-2.5 text-right">
                    <Money
                      paise={t.direction === "CREDIT" ? t.amount_paise : -t.amount_paise}
                      signed
                      exact
                      tone={t.direction === "CREDIT" ? "positive" : undefined}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <nav
            aria-label="Transaction pages"
            className="mt-4 flex items-center justify-between gap-3 text-sm"
          >
            <Button
              size="sm"
              disabled={page === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
            >
              Previous
            </Button>
            <span className="tnum text-[var(--fg-muted)]">
              {page * PAGE_SIZE + 1}–
              {Math.min((page + 1) * PAGE_SIZE, data.total)} of {data.total}
            </span>
            <Button
              size="sm"
              disabled={(page + 1) * PAGE_SIZE >= data.total}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </nav>
        </GlassPanel>
      ) : null}
    </div>
  );
}
