import { ApiError } from "./api";
import { getLanguage, translate as t } from "../i18n";

export type FieldErrors = Record<string, string>;

/** Translate only known validation messages; preserve the server's stored error. */
export function translateAccountMessage(message: string): string {
  if (getLanguage() === "en") return message;
  const translated = t(message);
  if (translated !== message) return translated;
  const suffix = " Refresh saved views before trying again.";
  if (message.endsWith(suffix))
    return (
      translateAccountMessage(message.slice(0, -suffix.length)) +
      " " +
      t(suffix.trim())
    );
  const short = message.match(
    /^This password is too short\. It must contain at least (\d+) characters\.(?:\s+|$)/,
  );
  if (short)
    return (
      t("This password must contain at least {count} characters.", {
        count: short[1],
      }) +
      (message.length > short[0].length
        ? " " + translateAccountMessage(message.slice(short[0].length))
        : "")
    );
  const length = message.match(
    /^Ensure this field has (no more|at least) (\d+) characters\.$/,
  );
  if (length)
    return t(
      length[1] === "no more"
        ? "Use no more than {count} characters."
        : "Use at least {count} characters.",
      { count: length[2] },
    );
  const similar = message.match(
    /^The password is too similar to the (username|email address)\.$/,
  );
  if (similar) return t("The password is too similar to your account details.");
  // DRF may return several validation sentences for one field.
  const parts = message.split(/(?<=\.)\s+(?=[A-Z])/);
  return parts.length > 1
    ? parts.map(translateAccountMessage).join(" ")
    : message;
}

export function accountErrors(
  value: unknown,
  fallback: string,
): { message: string; fields: FieldErrors } {
  const fields: FieldErrors = {};
  if (
    value instanceof ApiError &&
    value.details &&
    typeof value.details === "object" &&
    !Array.isArray(value.details)
  ) {
    for (const [key, detail] of Object.entries(value.details)) {
      const text =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail
                .filter((item): item is string => typeof item === "string")
                .join(" ")
            : "";
      if (text) fields[key] = text;
    }
  }
  return { message: value instanceof Error ? value.message : fallback, fields };
}
