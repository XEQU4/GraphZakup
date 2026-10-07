/** Format the API's decimal string without floating-point conversion. */
export function formatMoney(
  value: string | null | undefined,
  currency = "KZT",
): string {
  if (value == null || !/^-?\d+(?:\.\d+)?$/.test(value)) return "Not available";
  const negative = value.startsWith("-");
  const [rawInteger, fraction = ""] = (negative ? value.slice(1) : value).split(
    ".",
  );
  const integer = rawInteger.replace(/^0+(?=\d)/, "");
  const groups = integer.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const decimals = fraction.padEnd(2, "0");
  const sign = negative && /[1-9]/.test(integer + fraction) ? "-" : "";
  return `${sign}${groups}.${decimals} ${currency}`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "Not recorded";
  const date = new Date(value.length === 10 ? value + "T00:00:00Z" : value);
  if (
    !Number.isFinite(date.getTime()) ||
    (value.length === 10 && date.toISOString().slice(0, 10) !== value)
  )
    return "Not recorded";
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "Not recorded";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "Not recorded";
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Almaty",
  }).format(date);
}

/** Only explicit HTTP(S) references are navigable; source values are never HTML. */
export function safeHttpUrl(value: string | null | undefined): string | null {
  if (
    !value ||
    !/^https?:\/\//i.test(value) ||
    /[\s\\\u0000-\u001f\u007f]/.test(value)
  )
    return null;
  try {
    const url = new URL(value);
    if (
      !["http:", "https:"].includes(url.protocol) ||
      !url.hostname ||
      url.username ||
      url.password
    )
      return null;
    return url.href;
  } catch {
    return null;
  }
}

export function formatCount(value: number | null | undefined): string {
  return value == null || !Number.isFinite(value)
    ? "—"
    : new Intl.NumberFormat("en-GB").format(value);
}

export function cx(...values: (string | false | null | undefined)[]): string {
  return values.filter(Boolean).join(" ");
}

export const cn = cx;
