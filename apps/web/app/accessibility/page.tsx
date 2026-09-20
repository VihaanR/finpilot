import type { Metadata } from "next";
import { GlassPanel, SectionHeading } from "@/components/ui/Glass";

export const metadata: Metadata = {
  title: "Accessibility statement — FinPilot",
  description:
    "FinPilot's conformance target, the standards applied, what has been verified, and the limitations we know about.",
};

function Panel({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <GlassPanel as="section" className="p-6">
      <SectionHeading>{title}</SectionHeading>
      <div className="space-y-3 text-sm leading-relaxed text-[var(--fg-muted)]">
        {children}
      </div>
    </GlassPanel>
  );
}

export default function AccessibilityPage() {
  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      <div>
        <SectionHeading as="h1">Accessibility statement</SectionHeading>
        <p className="max-w-2xl text-[var(--fg-muted)]">
          Financial software that a blind person cannot operate is financial
          software that excludes them from their own money. This page states
          what FinPilot targets, what has actually been checked, and what has
          not.
        </p>
      </div>

      <Panel title="Conformance target">
        <p>
          FinPilot targets <strong className="text-[var(--fg)]">WCAG 2.1 Level AA</strong>,
          and is built to align with <strong className="text-[var(--fg)]">IS 17802</strong>{" "}
          (the Indian standard for ICT accessibility) and{" "}
          <strong className="text-[var(--fg)]">GIGW 3.0</strong>.
        </p>
        <p>
          This is a <em>target</em>, not a certification. No third party has
          audited this product.
        </p>
      </Panel>

      <Panel title="Why this is not optional">
        <p>
          On 30 April 2025, in{" "}
          <em>Pragya Prasun v. Union of India</em> and{" "}
          <em>Amar Jain v. Union of India</em>, the Supreme Court held that
          digital accessibility is an intrinsic component of the right to life
          under <strong className="text-[var(--fg)]">Article 21</strong> of the
          Constitution. The case concerned digital KYC processes that excluded
          blind, low-vision and acid-attack survivors from opening bank
          accounts.
        </p>
        <p>
          SEBI followed on 31 July 2025 with a circular mandating digital
          accessibility across all regulated entities, giving effect to the{" "}
          <strong className="text-[var(--fg)]">RPwD Act 2016, §§40–46</strong>,
          which requires ICT content in accessible formats.
        </p>
      </Panel>

      <Panel title="What is built in">
        <ul className="list-disc space-y-1.5 pl-5">
          <li>
            Every chart ships with a toggle to an equivalent data table with
            proper row and column headers. The chart is never the only way to
            read the figures.
          </li>
          <li>
            Every amount is announced in words: ₹18,400 is read as
            &ldquo;eighteen thousand four hundred rupees&rdquo;, not as a digit
            string.
          </li>
          <li>
            No status, badge or chart conveys meaning through colour alone.
            Every one carries a label or a shape as well.
          </li>
          <li>
            Skip-to-content is the first focusable element on every page, and
            every interactive element has a visible focus indicator.
          </li>
          <li>
            Dialogs trap focus, close on Escape, and return focus to whatever
            opened them.
          </li>
          <li>
            <code>prefers-reduced-motion</code> and{" "}
            <code>prefers-contrast: more</code> are both honoured. High contrast
            replaces the translucent glass surfaces with solid ones.
          </li>
          <li>
            The page declares <code>lang=&quot;en-IN&quot;</code> so
            assistive technology uses Indian English for numbers and dates.
          </li>
        </ul>
      </Panel>

      <Panel title="What has been verified, and what has not">
        <p>
          Verified: keyboard traversal of the shell and dialogs; the rendered
          screen-reader text for amounts; the presence of table alternatives on
          every chart.
        </p>
        <p className="text-[var(--fg)]">
          Not yet verified: an automated axe-core pass across every route in
          both themes, a full screen-reader run (NVDA or TalkBack), and testing
          at 200% browser zoom on small viewports. Until those are done, treat
          the claims above as intent backed by construction, not as measured
          conformance.
        </p>
      </Panel>

      <Panel title="Known limitations">
        <ul className="list-disc space-y-1.5 pl-5">
          <li>
            Charts are rendered with Recharts, whose SVG output is not fully
            keyboard-navigable. The table toggle exists because of this, not as
            a nicety.
          </li>
          <li>
            The interface is English only. Vernacular support via Bhashini is
            designed but not built.
          </li>
          <li>
            Uploaded PDF statements are parsed as text; scanned image-only
            statements are not yet readable.
          </li>
        </ul>
      </Panel>

      <Panel title="Feedback">
        <p>
          If any part of FinPilot is unusable for you, that is a defect and we
          want to hear about it. Raise an issue on the project repository, or
          contact the maintainer directly. Accessibility reports are treated as
          bugs, not as feature requests.
        </p>
      </Panel>
    </div>
  );
}
