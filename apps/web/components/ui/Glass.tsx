import { cn } from "@/lib/cn";

/**
 * The one glass surface in the product.
 *
 * Every panel goes through here so the blur, the hairline and the shadow stay
 * identical everywhere, and so `prefers-contrast: more` can drop all three in
 * one place by swapping the CSS variables.
 */
export function GlassPanel({
  as: Tag = "div",
  className,
  strong,
  children,
  ...rest
}: {
  as?: "div" | "section" | "article" | "aside" | "nav" | "header";
  className?: string;
  strong?: boolean;
  children: React.ReactNode;
} & React.HTMLAttributes<HTMLElement>) {
  return (
    <Tag
      className={cn(
        "rounded-[var(--radius)] border backdrop-blur-[var(--glass-blur)]",
        "border-[var(--glass-border)] shadow-[var(--glass-shadow)]",
        strong ? "bg-[var(--glass-strong)]" : "bg-[var(--glass)]",
        className,
      )}
      {...rest}
    >
      {children}
    </Tag>
  );
}

export function SectionHeading({
  children,
  hint,
  as: Tag = "h2",
  id,
}: {
  children: React.ReactNode;
  hint?: React.ReactNode;
  as?: "h1" | "h2" | "h3";
  id?: string;
}) {
  return (
    <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
      <Tag
        id={id}
        className={cn(
          "font-[family-name:var(--font-display)] tracking-tight text-[var(--fg)]",
          Tag === "h1" ? "text-3xl sm:text-4xl" : "text-xl",
        )}
      >
        {children}
      </Tag>
      {hint ? <p className="text-sm text-[var(--fg-muted)]">{hint}</p> : null}
    </div>
  );
}
