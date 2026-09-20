"use client";

import { useState } from "react";
import { GlassPanel, SectionHeading } from "@/components/ui/Glass";
import { Button } from "@/components/ui/Button";
import { Pill } from "@/components/ui/Badge";
import { ErrorPanel, LoadingPanel } from "@/components/ui/States";
import { API_BASE, api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { formatDate, titleCase } from "@/lib/format";
import type { Vault } from "@/lib/types";

export default function VaultPage() {
  const { data, error, loading, reload } = useApi<Vault>("/api/vault");
  const [notice, setNotice] = useState("");
  const [confirm, setConfirm] = useState("");
  const [erasing, setErasing] = useState(false);

  async function setScope(scope: string, granted: boolean) {
    try {
      await api.post("/api/vault/consent", { scope, granted });
      setNotice(
        granted
          ? `Consent granted for ${titleCase(scope)}.`
          : scope === "ai_processing"
            ? "AI processing revoked. Every figure on the dashboard keeps working — the engine does not need it."
            : `Consent revoked for ${titleCase(scope)}.`,
      );
      reload();
    } catch (e) {
      setNotice((e as Error).message);
    }
  }

  async function erase() {
    setErasing(true);
    try {
      await api.post("/api/vault/erase", { confirm });
      setNotice("Everything has been deleted.");
      setConfirm("");
      reload();
    } catch (e) {
      setNotice((e as Error).message);
    } finally {
      setErasing(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6">
      <div>
        <SectionHeading as="h1">Data vault</SectionHeading>
        <p className="max-w-2xl text-[var(--fg-muted)]">
          What is held, who it reaches, and what leaves this machine. Both
          buttons on this page do exactly what they say — erase really deletes.
        </p>
      </div>

      {error ? <ErrorPanel message={error} /> : null}
      {loading && !data ? <LoadingPanel label="Reading the consent ledger…" /> : null}

      <p aria-live="polite" className="text-sm text-[var(--positive)]">
        {notice}
      </p>

      {data ? (
        <>
          <GlassPanel as="section" className="p-6">
            <SectionHeading>Your consents</SectionHeading>
            <ul className="space-y-3">
              {Object.entries(data.scopes).map(([scope, granted]) => (
                <li
                  key={scope}
                  className="flex flex-wrap items-start justify-between gap-3"
                >
                  <span className="min-w-0 flex-1 basis-64">
                    <span className="block text-sm text-[var(--fg)]">
                      {titleCase(scope)}
                    </span>
                    <span className="block text-xs text-[var(--fg-subtle)]">
                      {scope === "ai_processing"
                        ? "Lets redacted text reach Google's Gemini API. Revoking it disables AI features; every number on the dashboard keeps working."
                        : "Lets FinPilot store and analyse your statements at all."}
                    </span>
                  </span>
                  <span className="flex shrink-0 items-center gap-3">
                    <Pill tone={granted ? "info" : "muted"}>
                      {granted ? "Granted" : "Revoked"}
                    </Pill>
                    <Button size="sm" onClick={() => setScope(scope, !granted)}>
                      {granted ? "Revoke" : "Grant"}
                      <span className="sr-only"> {titleCase(scope)}</span>
                    </Button>
                  </span>
                </li>
              ))}
            </ul>

            {!data.ai_configured ? (
              <p className="mt-4 text-xs text-[var(--fg-subtle)]">
                No AI key is configured on this instance, so no request has ever
                left it regardless of consent.
              </p>
            ) : null}
          </GlassPanel>

          <GlassPanel as="section" className="p-6">
            <SectionHeading>What redaction actually does</SectionHeading>
            <p className="text-sm text-[var(--fg-muted)]">{data.redaction_example.note}</p>
            <dl className="mt-3 space-y-2 text-sm">
              <div>
                <dt className="text-xs uppercase tracking-wider text-[var(--fg-subtle)]">
                  On this machine
                </dt>
                <dd className="mt-0.5 break-all rounded-[var(--radius-sm)] border border-[var(--border)] p-2 font-mono text-xs text-[var(--fg)]">
                  {data.redaction_example.before}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wider text-[var(--fg-subtle)]">
                  What would be sent
                </dt>
                <dd className="mt-0.5 break-all rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--primary-soft)] p-2 font-mono text-xs text-[var(--fg)]">
                  {data.redaction_example.after}
                </dd>
              </div>
            </dl>
          </GlassPanel>

          <GlassPanel as="section" className="p-6">
            <SectionHeading>Consent artefact</SectionHeading>
            <dl className="space-y-3 text-sm">
              <Row label="Purpose">{data.consent_artefact.purpose}</Row>
              <Row label="Data types">
                {data.consent_artefact.data_types.join(", ")}
              </Row>
              <Row label="Processing">
                {data.consent_artefact.processing.join(", ")}
              </Row>
              <Row label="Who else receives it">
                <ul className="space-y-1">
                  {data.consent_artefact.third_parties.map((p) => (
                    <li key={p.name}>
                      <span className="text-[var(--fg)]">{p.name}</span> — {p.role}{" "}
                      ({p.region})
                    </li>
                  ))}
                </ul>
              </Row>
              <Row label="Retention">{data.consent_artefact.retention}</Row>
              <Row label="Revocation">{data.consent_artefact.revocation}</Row>
            </dl>
          </GlassPanel>

          <GlassPanel as="section" className="p-6">
            <SectionHeading hint={`${data.retention_days} day retention`}>
              What is stored
            </SectionHeading>
            <table className="w-full border-collapse text-sm">
              <caption className="sr-only">
                Rows held per table, and the oldest record in each
              </caption>
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs uppercase tracking-wider text-[var(--fg-subtle)]">
                  <th scope="col" className="py-2 font-medium">Table</th>
                  <th scope="col" className="py-2 text-right font-medium">Rows</th>
                </tr>
              </thead>
              <tbody>
                {data.storage_inventory.map((row) => (
                  <tr key={row.table} className="border-b border-[var(--border)]">
                    <th scope="row" className="py-2 text-left font-normal text-[var(--fg)]">
                      {titleCase(row.table)}
                    </th>
                    <td className="tnum py-2 text-right text-[var(--fg-muted)]">
                      {row.rows}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </GlassPanel>

          <GlassPanel as="section" className="p-6">
            <SectionHeading hint={`${data.disclosures.length} recorded`}>
              AI disclosure log
            </SectionHeading>
            {data.disclosures.length === 0 ? (
              <p className="text-sm text-[var(--fg-muted)]">
                No AI call has been made. When one is, this log records which
                field <em>names</em> were sent — never the values.
              </p>
            ) : (
              <ul className="space-y-2 text-sm">
                {data.disclosures.map((d) => (
                  <li key={d.id} className="border-b border-[var(--border)] pb-2">
                    <span className="text-[var(--fg)]">{d.purpose}</span>{" "}
                    <span className="text-[var(--fg-subtle)]">
                      · {d.provider} · {d.model} ·{" "}
                      {formatDate(d.created_at.slice(0, 10))}
                    </span>
                    <span className="block text-xs text-[var(--fg-muted)]">
                      {d.field_types.length > 0
                        ? `Redacted before sending: ${d.field_types.join(", ")} (${d.redacted_count} value${d.redacted_count === 1 ? "" : "s"})`
                        : "Nothing identifying was present to redact."}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </GlassPanel>

          <GlassPanel as="section" className="p-6">
            <SectionHeading>Your rights</SectionHeading>

            <div className="space-y-5">
              <div>
                <h3 className="text-sm font-medium text-[var(--fg)]">
                  Take everything with you
                </h3>
                <p className="mt-1 text-sm text-[var(--fg-muted)]">
                  Transactions, goals, budgets, documents and your full consent
                  history, as JSON.
                </p>
                <a
                  href={API_BASE + "/api/vault/export"}
                  download="finpilot-export.json"
                  className="mt-2 inline-block rounded-full border border-[var(--border-strong)] px-4 py-2 text-sm text-[var(--fg)] hover:bg-[var(--primary-soft)]"
                >
                  Export everything
                </a>
              </div>

              <div className="border-t border-[var(--border)] pt-5">
                <h3 className="text-sm font-medium text-[var(--critical)]">
                  <span aria-hidden="true">▲ </span>Erase everything
                </h3>
                <p className="mt-1 text-sm text-[var(--fg-muted)]">
                  Deletes every transaction, document, goal, budget and consent
                  record. This cannot be undone.
                </p>
                <label
                  htmlFor="erase-confirm"
                  className="mt-3 block text-sm text-[var(--fg)]"
                >
                  Type DELETE to confirm
                </label>
                <input
                  id="erase-confirm"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  className="mt-1 w-48 rounded-[var(--radius-sm)] border border-[var(--border-strong)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--fg)]"
                />
                <div className="mt-3">
                  <Button
                    variant="danger"
                    disabled={confirm.trim().toUpperCase() !== "DELETE" || erasing}
                    onClick={erase}
                  >
                    {erasing ? "Deleting…" : "Erase everything"}
                  </Button>
                </div>
              </div>
            </div>
          </GlassPanel>
        </>
      ) : null}
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 sm:grid-cols-[10rem_1fr]">
      <dt className="text-xs uppercase tracking-wider text-[var(--fg-subtle)]">
        {label}
      </dt>
      <dd className="text-[var(--fg-muted)]">{children}</dd>
    </div>
  );
}
