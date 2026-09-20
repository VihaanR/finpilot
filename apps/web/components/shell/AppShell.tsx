"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/cn";
import { ThemeToggle } from "./ThemeToggle";

const NAV = [
  { href: "/", label: "Dashboard", glyph: "◈" },
  { href: "/chat", label: "Ask FinPilot", glyph: "✦" },
  { href: "/radar", label: "Mandate Radar", glyph: "◎" },
  { href: "/goals", label: "Goals & simulator", glyph: "◇" },
  { href: "/transactions", label: "Transactions", glyph: "☰" },
  { href: "/upload", label: "Upload statement", glyph: "↑" },
  { href: "/vault", label: "Data vault", glyph: "⌸" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="min-h-dvh">
      {/* First focusable element on every page (DESIGN.md 11). */}
      <a
        href="#main"
        className={cn(
          "sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[60]",
          "focus:rounded-full focus:border focus:border-[var(--border-strong)]",
          "focus:bg-[var(--surface)] focus:px-4 focus:py-2 focus:text-sm focus:text-[var(--fg)]",
        )}
      >
        Skip to main content
      </a>

      <div className="mx-auto flex min-h-dvh w-full max-w-[110rem] flex-col lg:flex-row">
        <header className="lg:sticky lg:top-0 lg:h-dvh lg:w-72 lg:shrink-0 lg:py-6 lg:pl-6">
          <div
            className={cn(
              "flex h-full flex-col gap-6 border-b px-5 py-4",
              "border-[var(--glass-border)] bg-[var(--glass)] backdrop-blur-[var(--glass-blur)]",
              "lg:rounded-[var(--radius)] lg:border lg:px-5 lg:py-6 lg:shadow-[var(--glass-shadow)]",
            )}
          >
            <div className="flex items-center justify-between gap-3">
              <Link href="/" className="group flex items-baseline gap-2">
                <span className="font-[family-name:var(--font-display)] text-2xl tracking-tight text-[var(--fg)]">
                  FinPilot
                </span>
                <span className="text-[0.65rem] uppercase tracking-[0.2em] text-[var(--accent)]">
                  India
                </span>
              </Link>
              <div className="lg:hidden">
                <ThemeToggle />
              </div>
            </div>

            <nav aria-label="Primary" className="flex-1">
              <ul className="flex flex-wrap gap-1 lg:flex-col lg:gap-0.5">
                {NAV.map((item) => {
                  const active =
                    item.href === "/"
                      ? pathname === "/"
                      : pathname.startsWith(item.href);
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        aria-current={active ? "page" : undefined}
                        className={cn(
                          "flex items-center gap-3 rounded-full px-3 py-2 text-sm transition-colors",
                          active
                            ? "bg-[var(--primary-soft)] font-medium text-[var(--fg)]"
                            : "text-[var(--fg-muted)] hover:bg-[var(--primary-soft)] hover:text-[var(--fg)]",
                        )}
                      >
                        <span
                          aria-hidden="true"
                          className={cn(
                            "text-base",
                            active ? "text-[var(--accent)]" : "text-[var(--fg-subtle)]",
                          )}
                        >
                          {item.glyph}
                        </span>
                        {item.label}
                        {/* Current page is not signalled by colour alone. */}
                        {active ? <span className="sr-only"> (current page)</span> : null}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </nav>

            <div className="hidden flex-col gap-3 lg:flex">
              <ThemeToggle />
              <p className="text-xs leading-relaxed text-[var(--fg-subtle)]">
                FinPilot shows you your own numbers. It does not give investment
                or financial advice.
              </p>
              <Link
                href="/accessibility"
                className="text-xs text-[var(--fg-muted)] underline underline-offset-4 hover:text-[var(--fg)]"
              >
                Accessibility statement
              </Link>
            </div>
          </div>
        </header>

        <main id="main" tabIndex={-1} className="flex-1 px-4 py-6 sm:px-6 lg:py-8">
          {children}
        </main>
      </div>

      <footer className="border-t border-[var(--border)] px-6 py-6 text-xs text-[var(--fg-subtle)] lg:hidden">
        <Link href="/accessibility" className="underline underline-offset-4">
          Accessibility statement
        </Link>
        <p className="mt-2">
          FinPilot does not give investment or financial advice.
        </p>
      </footer>
    </div>
  );
}
