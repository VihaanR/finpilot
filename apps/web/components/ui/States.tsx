import Link from "next/link";
import { GlassPanel } from "./Glass";

export function LoadingPanel({ label }: { label: string }) {
  return (
    <GlassPanel className="p-6">
      <p className="text-sm text-[var(--fg-muted)]" aria-live="polite">
        {label}
      </p>
    </GlassPanel>
  );
}

/**
 * A failed fetch nearly always means the API is not running locally, so the
 * error state says that rather than surfacing a bare network message.
 */
export function ErrorPanel({ message }: { message: string }) {
  return (
    <GlassPanel className="border-[var(--critical)] p-6">
      <p role="alert" className="text-sm text-[var(--fg)]">
        <span className="font-medium text-[var(--critical)]">
          <span aria-hidden="true">▲ </span>Could not load this.
        </span>{" "}
        {message}
      </p>
      <p className="mt-2 text-sm text-[var(--fg-muted)]">
        If you are running FinPilot locally, start the API with{" "}
        <code className="rounded bg-[var(--primary-soft)] px-1.5 py-0.5">
          uvicorn app.main:app --reload
        </code>{" "}
        from <code>services/api</code>.
      </p>
    </GlassPanel>
  );
}

export function EmptyPanel({
  title,
  children,
}: {
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <GlassPanel className="p-6 text-center">
      <p className="font-[family-name:var(--font-display)] text-lg text-[var(--fg)]">
        {title}
      </p>
      <p className="mx-auto mt-2 max-w-md text-sm text-[var(--fg-muted)]">
        {children ?? (
          <>
            Upload a bank statement to fill this in, or load the demo ledger to
            see what it looks like with fourteen months of data.
          </>
        )}
      </p>
      <p className="mt-4 flex flex-wrap justify-center gap-3 text-sm">
        <Link
          href="/upload"
          className="rounded-full border border-[var(--border-strong)] px-4 py-2 text-[var(--fg)] hover:bg-[var(--primary-soft)]"
        >
          Upload a statement
        </Link>
      </p>
    </GlassPanel>
  );
}
