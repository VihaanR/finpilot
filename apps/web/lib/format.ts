/** Money formatting. Paise in, rupees out — and only ever at this boundary. */

const UNITS = [
  "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
  "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
  "sixteen", "seventeen", "eighteen", "nineteen",
];
const TENS = [
  "", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty",
  "ninety",
];

function underThousand(n: number): string {
  if (n < 20) return UNITS[n];
  if (n < 100) {
    const rest = n % 10;
    return TENS[Math.floor(n / 10)] + (rest ? " " + UNITS[rest] : "");
  }
  const rest = n % 100;
  return UNITS[Math.floor(n / 100)] + " hundred" + (rest ? " " + underThousand(rest) : "");
}

/**
 * Indian numbering, in words: 1,84,00,000 reads as "one crore eighty-four lakh".
 *
 * A screen reader given "₹18,400" announces the glyph and then the digits, and
 * listeners routinely mishear the magnitude — which is the one thing that
 * matters about a financial figure. DESIGN.md 11 requires the words.
 */
export function rupeesInWords(paise: number): string {
  const negative = paise < 0;
  const whole = Math.floor(Math.abs(paise) / 100);
  const fraction = Math.abs(paise) % 100;

  const parts: string[] = [];
  let remaining = whole;

  const crore = Math.floor(remaining / 10_000_000);
  remaining %= 10_000_000;
  const lakh = Math.floor(remaining / 100_000);
  remaining %= 100_000;
  const thousand = Math.floor(remaining / 1000);
  remaining %= 1000;

  if (crore) parts.push(underThousand(crore) + " crore");
  if (lakh) parts.push(underThousand(lakh) + " lakh");
  if (thousand) parts.push(underThousand(thousand) + " thousand");
  if (remaining) parts.push(underThousand(remaining));
  if (!parts.length) parts.push("zero");

  let spoken = parts.join(" ") + " rupees";
  if (fraction) spoken += " and " + underThousand(fraction) + " paise";
  return (negative ? "minus " : "") + spoken;
}

const INR = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});
const INR_PAISE = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatPaise(paise: number, opts: { paise?: boolean } = {}): string {
  return opts.paise ? INR_PAISE.format(paise / 100) : INR.format(Math.round(paise / 100));
}

/** Compact form for axis ticks only, never for a figure a decision rests on. */
export function compactPaise(paise: number): string {
  const rupees = Math.round(paise / 100);
  const abs = Math.abs(rupees);
  if (abs >= 10_000_000) return `₹${(rupees / 10_000_000).toFixed(1)}Cr`;
  if (abs >= 100_000) return `₹${(rupees / 100_000).toFixed(1)}L`;
  if (abs >= 1000) return `₹${Math.round(rupees / 1000)}k`;
  return `₹${rupees}`;
}

export function formatDate(iso: string): string {
  const d = new Date(iso + (iso.length === 10 ? "T00:00:00" : ""));
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export function formatDayMonth(iso: string): string {
  const d = new Date(iso + (iso.length === 10 ? "T00:00:00" : ""));
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

/** Accepts both "2026-09" and "2026-09-01"; the API returns the latter. */
export function formatMonth(
  month: string,
  style: "long" | "short" = "long",
): string {
  const iso = month.length === 7 ? month + "-01" : month;
  return new Date(iso + "T00:00:00").toLocaleDateString("en-IN", {
    month: style,
    year: style === "long" ? "numeric" : "2-digit",
  });
}

/** Slugs carry financial acronyms; title-casing them blind gives "Emi", "Ai". */
const ACRONYMS = new Set([
  "ai", "upi", "emi", "sip", "mf", "atm", "neft", "imps", "rtgs", "nach",
  "pos", "kyc", "otp", "rbi", "ifsc", "pan", "epf", "ppf", "nps", "ott",
]);

export function titleCase(slug: string): string {
  return slug
    .split(/[_\s-]+/)
    .map((w) =>
      ACRONYMS.has(w.toLowerCase())
        ? w.toUpperCase()
        : w.charAt(0).toUpperCase() + w.slice(1).toLowerCase(),
    )
    .join(" ");
}
