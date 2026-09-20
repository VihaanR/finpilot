"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { GlassPanel, SectionHeading } from "@/components/ui/Glass";
import { Button } from "@/components/ui/Button";
import { API_BASE, api } from "@/lib/api";
import { cn } from "@/lib/cn";

interface BankHint {
  bank_code: string;
  bank_name: string;
  formats: string[];
  example: string;
}

interface IngestEvent {
  stage: string;
  message?: string;
  ok?: boolean;
  code?: string;
  hint?: string;
  result?: {
    inserted: number;
    duplicates: number;
    total: number;
    adapter_name?: string;
    confidence?: number;
  };
}

const STAGES = [
  "received",
  "decrypt",
  "extract",
  "detect",
  "parsed",
  "normalise",
  "categorise",
  "dedupe",
  "stored",
  "done",
];

export default function UploadPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [password, setPassword] = useState("");
  const [bank, setBank] = useState("");
  const [hints, setHints] = useState<BankHint[]>([]);
  const [events, setEvents] = useState<IngestEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api
      .get<{ banks: BankHint[] }>("/api/banks/password-hints")
      .then((d) => setHints(d.banks))
      .catch(() => setHints([]));
  }, []);

  const selectedHint = hints.find((h) => h.bank_code === bank);

  function addFiles(list: FileList | null) {
    if (!list) return;
    setFiles((prev) => [...prev, ...Array.from(list)]);
  }

  /**
   * Files go one at a time, deliberately. Each statement gets its own
   * document row and its own progress stream, and a failure on the third file
   * must not discard the two that already landed.
   */
  async function run() {
    if (!files.length || running) return;
    setRunning(true);
    setEvents([]);

    for (const file of files) {
      const form = new FormData();
      form.append("file", file);
      if (password) form.append("password", password);

      setEvents((prev) => [
        ...prev,
        { stage: "received", message: `Reading ${file.name}…` },
      ]);

      try {
        const response = await fetch(API_BASE + "/api/ingest", {
          method: "POST",
          body: form,
        });
        if (!response.ok || !response.body) {
          throw new Error(`Upload failed (${response.status}).`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const frames = buffer.split("\n\n");
          buffer = frames.pop() ?? "";
          for (const frame of frames) {
            const line = frame
              .split("\n")
              .find((l) => l.startsWith("data:"));
            if (!line) continue;
            try {
              const payload = JSON.parse(line.slice(5).trim()) as IngestEvent;
              setEvents((prev) => [...prev, payload]);
            } catch {
              // A partial frame; the next read will complete it.
            }
          }
        }
      } catch (e) {
        setEvents((prev) => [
          ...prev,
          { stage: "error", message: (e as Error).message },
        ]);
      }
    }

    setFiles([]);
    setRunning(false);
  }

  const last = events[events.length - 1];
  const finished = last?.stage === "done";
  const result = events.find((e) => e.result)?.result;
  const failure = events.find((e) => e.stage === "error");

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      <div>
        <SectionHeading as="h1">Upload a statement</SectionHeading>
        <p className="max-w-2xl text-[var(--fg-muted)]">
          CSV, XLSX or PDF, including password-protected PDFs. Uploading the
          same file twice is safe: every row is keyed, so a re-upload adds
          nothing.
        </p>
      </div>

      <GlassPanel className="p-6">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            addFiles(e.dataTransfer.files);
          }}
          className={cn(
            "rounded-[var(--radius)] border-2 border-dashed p-8 text-center transition-colors",
            dragging
              ? "border-[var(--accent)] bg-[var(--accent-soft)]"
              : "border-[var(--border-strong)]",
          )}
        >
          <p className="text-[var(--fg-muted)]">
            Drag statements here, or
          </p>
          <div className="mt-3">
            <Button variant="primary" onClick={() => inputRef.current?.click()}>
              Choose files
            </Button>
          </div>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept=".csv,.xlsx,.xls,.pdf,.txt"
            className="sr-only"
            aria-label="Statement files to upload"
            onChange={(e) => addFiles(e.target.files)}
          />
        </div>

        {files.length > 0 ? (
          <ul className="mt-4 space-y-1 text-sm">
            {files.map((f, i) => (
              <li key={f.name + i} className="flex items-center justify-between gap-3">
                <span className="text-[var(--fg)]">{f.name}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setFiles((prev) => prev.filter((_, j) => j !== i))}
                >
                  Remove
                  <span className="sr-only"> {f.name}</span>
                </Button>
              </li>
            ))}
          </ul>
        ) : null}

        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          <div>
            <label
              htmlFor="bank"
              className="block text-sm font-medium text-[var(--fg)]"
            >
              Which bank is this from?
            </label>
            <select
              id="bank"
              value={bank}
              onChange={(e) => setBank(e.target.value)}
              className="mt-1 w-full rounded-[var(--radius-sm)] border border-[var(--border-strong)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--fg)]"
            >
              <option value="">Not sure / other</option>
              {hints.map((h) => (
                <option key={h.bank_code} value={h.bank_code}>
                  {h.bank_name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label
              htmlFor="pdf-password"
              className="block text-sm font-medium text-[var(--fg)]"
            >
              PDF password{" "}
              <span className="font-normal text-[var(--fg-subtle)]">
                (only if locked)
              </span>
            </label>
            <input
              id="pdf-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-describedby={selectedHint ? "password-hint" : undefined}
              className="mt-1 w-full rounded-[var(--radius-sm)] border border-[var(--border-strong)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--fg)]"
            />
          </div>
        </div>

        {selectedHint ? (
          <div
            id="password-hint"
            className="mt-3 rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--primary-soft)] p-3 text-sm"
          >
            <p className="font-medium text-[var(--fg)]">
              {selectedHint.bank_name} usually uses:
            </p>
            <ul className="mt-1 list-disc space-y-0.5 pl-5 text-[var(--fg-muted)]">
              {selectedHint.formats.map((f) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
            {selectedHint.example ? (
              <p className="mt-1 text-xs text-[var(--fg-subtle)]">
                For example: {selectedHint.example}
              </p>
            ) : null}
          </div>
        ) : null}

        <p className="mt-4 text-xs text-[var(--fg-subtle)]">
          The password is used in memory to open the file and is never stored.
        </p>

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <Button
            variant="primary"
            disabled={!files.length || running}
            onClick={run}
          >
            {running
              ? "Reading…"
              : files.length
                ? `Ingest ${files.length} ${files.length === 1 ? "file" : "files"}`
                : "Ingest"}
          </Button>
          <Link
            href="/"
            className="text-sm text-[var(--fg-muted)] underline underline-offset-4 hover:text-[var(--fg)]"
          >
            Back to dashboard
          </Link>
        </div>
      </GlassPanel>

      {events.length > 0 ? (
        <GlassPanel className="p-6">
          <SectionHeading>Progress</SectionHeading>

          <ol className="space-y-1 text-sm" aria-live="polite">
            {events.map((e, i) => (
              <li
                key={i}
                className={cn(
                  "flex gap-3",
                  e.stage === "error"
                    ? "text-[var(--critical)]"
                    : "text-[var(--fg-muted)]",
                )}
              >
                <span
                  aria-hidden="true"
                  className="w-4 shrink-0 text-[var(--accent)]"
                >
                  {e.stage === "error" ? "▲" : STAGES.includes(e.stage) ? "·" : "·"}
                </span>
                <span>
                  <span className="text-[var(--fg)]">{e.stage}</span>
                  {e.message ? ` — ${e.message}` : ""}
                </span>
              </li>
            ))}
          </ol>

          {failure ? (
            <p role="alert" className="mt-4 text-sm text-[var(--critical)]">
              {failure.message}
              {failure.hint ? ` ${failure.hint}` : ""}
            </p>
          ) : null}

          {finished && result ? (
            <div className="mt-4 border-t border-[var(--border)] pt-4 text-sm">
              <p className="text-[var(--fg)]">
                <span className="tnum font-medium">{result.inserted}</span> new
                transactions added,{" "}
                <span className="tnum font-medium">{result.duplicates}</span>{" "}
                already on file.
              </p>
              {result.adapter_name ? (
                <p className="mt-1 text-xs text-[var(--fg-subtle)]">
                  Read by the {result.adapter_name} adapter at{" "}
                  {Math.round((result.confidence ?? 0) * 100)}% confidence.
                </p>
              ) : null}
              <Link
                href="/"
                className="mt-3 inline-block rounded-full border border-[var(--border-strong)] px-4 py-2 text-[var(--fg)] hover:bg-[var(--primary-soft)]"
              >
                See the dashboard
              </Link>
            </div>
          ) : null}
        </GlassPanel>
      ) : null}

      <GlassPanel className="p-6">
        <SectionHeading>Nothing to hand?</SectionHeading>
        <p className="text-sm text-[var(--fg-muted)]">
          Load fourteen months of a synthetic Indian ledger and explore the
          whole product. This replaces whatever is currently stored.
        </p>
        <DemoResetButton />
      </GlassPanel>
    </div>
  );
}

function DemoResetButton() {
  const [state, setState] = useState<"idle" | "busy" | "done" | "error">("idle");
  const [message, setMessage] = useState("");

  async function reset() {
    setState("busy");
    try {
      const r = await api.post<{ inserted: number }>("/api/demo/reset");
      setMessage(`Loaded ${r.inserted} transactions.`);
      setState("done");
    } catch (e) {
      setMessage((e as Error).message);
      setState("error");
    }
  }

  return (
    <div className="mt-3">
      <Button onClick={reset} disabled={state === "busy"}>
        {state === "busy" ? "Loading demo data…" : "Load demo data"}
      </Button>
      <p
        aria-live="polite"
        className={cn(
          "mt-2 text-sm",
          state === "error" ? "text-[var(--critical)]" : "text-[var(--fg-muted)]",
        )}
      >
        {message}
      </p>
    </div>
  );
}
