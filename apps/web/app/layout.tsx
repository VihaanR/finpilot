import type { Metadata } from "next";
import { Fraunces, Inter } from "next/font/google";
import "./globals.css";
import { AppShell } from "@/components/shell/AppShell";
import { CitationProvider } from "@/components/citations/CitationContext";

const display = Fraunces({
  variable: "--font-display",
  subsets: ["latin"],
  display: "swap",
  axes: ["SOFT", "WONK"],
});

const body = Inter({
  variable: "--font-body",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "FinPilot — your committed money, explained",
  description:
    "Ingests your bank statements, finds every recurring mandate, and shows what is already committed before your next salary. Every figure is clickable down to the transactions behind it.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    // en-IN so screen readers use Indian English for numbers and dates.
    <html lang="en-IN" suppressHydrationWarning>
      <head>
        {/*
          Applies the stored theme before first paint. Without this the page
          flashes the system theme, which is worse than a little inline script.
        */}
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem('finpilot-theme');if(t==='light'||t==='dark')document.documentElement.setAttribute('data-theme',t)}catch(e){}`,
          }}
        />
      </head>
      <body className={`${display.variable} ${body.variable} antialiased`}>
        <CitationProvider>
          <AppShell>{children}</AppShell>
        </CitationProvider>
      </body>
    </html>
  );
}
