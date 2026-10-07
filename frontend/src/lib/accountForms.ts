import { ApiError } from "./api";

export type FieldErrors = Record<string, string>;

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
