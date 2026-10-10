import { getLanguage, translate as t } from "../i18n";

export const BUSINESS_TIME_ZONE = "Asia/Qyzylorda";

/** Format the API's decimal string without floating-point conversion. */
export function formatMoney(
  value: string | null | undefined,
  currency = "KZT",
): string {
  if (value == null || !/^-?\d+(?:\.\d+)?$/.test(value))
    return t("Not available");
  const negative = value.startsWith("-");
  const [rawInteger, fraction = ""] = (negative ? value.slice(1) : value).split(
    ".",
  );
  const integer = rawInteger.replace(/^0+(?=\d)/, "");
  const russian = getLanguage() === "ru";
  const groups = integer.replace(
    /\B(?=(\d{3})+(?!\d))/g,
    russian ? "\u00a0" : ",",
  );
  const decimals = fraction.padEnd(2, "0");
  const sign = negative && /[1-9]/.test(integer + fraction) ? "-" : "";
  return `${sign}${groups}${russian ? "," : "."}${decimals} ${currency}`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return t("Not recorded");
  const date = new Date(value.length === 10 ? value + "T00:00:00Z" : value);
  if (
    !Number.isFinite(date.getTime()) ||
    (value.length === 10 && date.toISOString().slice(0, 10) !== value)
  )
    return t("Not recorded");
  return new Intl.DateTimeFormat(getLanguage() === "ru" ? "ru-RU" : "en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    // A source calendar date is not an instant and must never shift day.
    timeZone: value.length === 10 ? "UTC" : BUSINESS_TIME_ZONE,
  }).format(date);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return t("Not recorded");
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return t("Not recorded");
  return new Intl.DateTimeFormat(getLanguage() === "ru" ? "ru-RU" : "en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: BUSINESS_TIME_ZONE,
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
    : new Intl.NumberFormat(getLanguage() === "ru" ? "ru-RU" : "en-GB").format(
        value,
      );
}

export function cx(...values: (string | false | null | undefined)[]): string {
  return values.filter(Boolean).join(" ");
}

export const cn = cx;
