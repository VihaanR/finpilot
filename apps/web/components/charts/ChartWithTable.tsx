"use client";

import { useId, useState } from "react";
import { cn } from "@/lib/cn";
import { Button } from "@/components/ui/Button";

export interface TableColumn<Row> {
  key: string;
  header: string;
  /** Rendered into a <td>. Row headers come from `rowHeader` instead. */
  cell: (row: Row) => React.ReactNode;
  numeric?: boolean;
}

/**
 * The mandatory wrapper for every chart in the product (BUILD_TASKS T08).
 *
 * A chart is a picture of a table. This renders both from the same data and
 * lets the reader switch, which is the difference between an accessible chart
 * and a chart with an alt attribute. The table is a real `<table>` with
 * `scope` on its headers, so it is navigable cell by cell.
 */
export function ChartWithTable<Row>({
  title,
  description,
  rows,
  columns,
  rowHeader,
  rowKey,
  children,
  className,
}: {
  title: string;
  description?: string;
  rows: Row[];
  columns: TableColumn<Row>[];
  /** The first cell of each body row, rendered as `<th scope="row">`. */
  rowHeader: { header: string; cell: (row: Row) => React.ReactNode };
  rowKey: (row: Row, index: number) => string;
  children: React.ReactNode;
  className?: string;
}) {
  const [showTable, setShowTable] = useState(false);
  const regionId = useId();

  return (
    <figure className={cn("m-0", className)}>
      <figcaption className="mb-3 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <span className="font-[family-name:var(--font-display)] text-lg text-[var(--fg)]">
          {title}
        </span>
        <Button
          variant="ghost"
          size="sm"
          aria-expanded={showTable}
          aria-controls={regionId}
          onClick={() => setShowTable((v) => !v)}
        >
          {showTable ? "Show chart" : "Show table"}
        </Button>
      </figcaption>

      {description ? (
        <p className="mb-3 text-sm text-[var(--fg-muted)]">{description}</p>
      ) : null}

      <div id={regionId}>
        {showTable ? (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <caption className="sr-only">{description ?? title}</caption>
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs uppercase tracking-wider text-[var(--fg-subtle)]">
                  <th scope="col" className="py-2 pr-3 font-medium">
                    {rowHeader.header}
                  </th>
                  {columns.map((col) => (
                    <th
                      key={col.key}
                      scope="col"
                      className={cn(
                        "py-2 pr-3 font-medium",
                        col.numeric && "text-right",
                      )}
                    >
                      {col.header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, index) => (
                  <tr key={rowKey(row, index)} className="border-b border-[var(--border)]">
                    <th scope="row" className="py-2 pr-3 text-left font-normal text-[var(--fg)]">
                      {rowHeader.cell(row)}
                    </th>
                    {columns.map((col) => (
                      <td
                        key={col.key}
                        className={cn(
                          "py-2 pr-3 text-[var(--fg-muted)]",
                          col.numeric && "text-right",
                        )}
                      >
                        {col.cell(row)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          // The chart itself is decorative once the table exists: the same
          // information is one keystroke away in a form a screen reader can
          // actually walk.
          <div role="img" aria-label={`${title}. ${description ?? ""} Use the Show table button for the underlying figures.`}>
            {children}
          </div>
        )}
      </div>
    </figure>
  );
}
