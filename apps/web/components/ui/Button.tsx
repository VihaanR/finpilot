import { cn } from "@/lib/cn";

const VARIANTS = {
  primary:
    "bg-[var(--primary)] text-[var(--primary-fg)] border-transparent hover:brightness-110",
  secondary:
    "bg-[var(--glass-strong)] text-[var(--fg)] border-[var(--border-strong)] hover:bg-[var(--glass)]",
  ghost:
    "bg-transparent text-[var(--fg-muted)] border-transparent hover:text-[var(--fg)] hover:bg-[var(--primary-soft)]",
  danger:
    "bg-transparent text-[var(--critical)] border-[var(--critical)] hover:bg-[var(--critical)]/10",
} as const;

export function Button({
  variant = "secondary",
  className,
  size = "md",
  ...rest
}: {
  variant?: keyof typeof VARIANTS;
  size?: "sm" | "md";
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-full border font-medium",
        "transition-[filter,background-color] disabled:cursor-not-allowed disabled:opacity-55",
        size === "sm" ? "px-3 py-1 text-xs" : "px-4 py-2 text-sm",
        VARIANTS[variant],
        className,
      )}
      {...rest}
    />
  );
}
