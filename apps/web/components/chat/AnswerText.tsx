"use client";

import { Fragment } from "react";
import { CitationChip } from "@/components/citations/CitationChip";

export type Citation = {
  id: string;
  label: string;
  value_paise: number;
  txn_ids: string[];
  txn_count: number;
};

/**
 * Renders the agent's prose, turning every cited figure into an openable chip.
 *
 * The model is asked to write `₹18,432 [c3]`. We find that pairing, drop the
 * marker from the visible text, and render the figure as a `CitationChip`
 * carrying the transaction ids the tool recorded.
 *
 * A figure with **no** marker is deliberately rendered in an "unverified"
 * state rather than silently as ordinary text. That is the visible half of
 * DESIGN.md §9.3: a hallucinated number has nowhere to hide, because the
 * absence of a citation is something the user can see.
 */

/** A rupee figure, optionally followed by its citation marker. */
const FIGURE = /((?:₹|Rs\.?\s?)\s?[\d,]+(?:\.\d{1,2})?)(\s*\[(c\d+)\])?/g;
/** A citation marker with no figure in front of it. */
const ORPHAN_MARKER = /\[c\d+\]/g;

function Unverified({ text }: { text: string }) {
  return (
    <span
      className="underline decoration-dotted decoration-[var(--caution)] underline-offset-4"
      title="This figure arrived without a citation, so it could not be traced to transactions."
    >
      {text}
      <span className="sr-only"> (unverified: no citation)</span>
    </span>
  );
}

/** Minimal inline markdown: **bold** only. The model is told to stay plain. */
function Inline({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {parts.map((part, i) =>
        part.startsWith("**") && part.endsWith("**") ? (
          <strong key={i} className="font-semibold">
            {part.slice(2, -2)}
          </strong>
        ) : (
          <Fragment key={i}>{part}</Fragment>
        ),
      )}
    </>
  );
}

function Line({ text, byId }: { text: string; byId: Map<string, Citation> }) {
  const nodes: React.ReactNode[] = [];
  let cursor = 0;
  let key = 0;

  for (const match of text.matchAll(FIGURE)) {
    const [whole, figure, , citationId] = match;
    const at = match.index ?? 0;
    if (at > cursor) {
      nodes.push(<Inline key={key++} text={text.slice(cursor, at)} />);
    }

    const citation = citationId ? byId.get(citationId) : undefined;
    if (citation && citation.txn_ids.length > 0) {
      nodes.push(
        <CitationChip
          key={key++}
          txnIds={citation.txn_ids}
          title={citation.label}
          subtitle={`${citation.txn_count} transaction${citation.txn_count === 1 ? "" : "s"}`}
        >
          <span>{figure}</span>
        </CitationChip>,
      );
    } else if (citation) {
      // A real citation with no rows behind it — a goal balance, say. The
      // figure is engine-computed and honest, it just has nothing to open.
      nodes.push(<Fragment key={key++}>{figure}</Fragment>);
    } else {
      nodes.push(<Unverified key={key++} text={figure} />);
    }
    cursor = at + whole.length;
  }

  if (cursor < text.length) {
    nodes.push(<Inline key={key++} text={text.slice(cursor).replace(ORPHAN_MARKER, "")} />);
  }
  return <>{nodes}</>;
}

export function AnswerText({
  text,
  citations,
}: {
  text: string;
  citations: Citation[];
}) {
  const byId = new Map(citations.map((c) => [c.id, c]));
  const lines = text.split("\n");

  return (
    <div className="space-y-2 leading-relaxed">
      {lines.map((line, i) =>
        line.trim() === "" ? null : (
          <p key={i} className={line.trimStart().match(/^(\d+\.|[-*])\s/) ? "pl-4" : ""}>
            <Line text={line} byId={byId} />
          </p>
        ),
      )}
    </div>
  );
}
