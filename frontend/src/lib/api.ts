import { useCallback, useEffect, useState } from "react";
export {
  formatMoney,
  formatDate,
  formatDateTime,
  safeHttpUrl,
  formatCount,
} from "./utils";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;

  constructor(
    message: string,
    status = 0,
    code = "network_error",
    details: unknown = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

const API_PREFIX = "/api/v1/";

export function apiPath(path: string): string {
  if (
    !path ||
    /[\u0000-\u0020\u007f\\#]/.test(path) ||
    path.includes("://") ||
    path.startsWith("//")
  ) {
    throw new ApiError("Invalid API route.", 0, "invalid_route");
  }
  const route = path.startsWith(API_PREFIX)
    ? path
    : path.startsWith("/")
      ? ""
      : API_PREFIX + path;
  const pathname = route.split("?")[0];
  // Reject encoded traversal too, so a URL constructor cannot silently leave the API boundary.
  let decoded = pathname;
  try {
    for (let pass = 0; pass < 3; pass++) decoded = decodeURIComponent(decoded);
  } catch {
    throw new ApiError("Invalid API route.", 0, "invalid_route");
  }
  if (
    !route ||
    /(?:^|\/)\.\.?(?:\/|$)/.test(decoded) ||
    /[\u0000-\u0020\u007f\\?#]/.test(decoded)
  ) {
    throw new ApiError("Invalid API route.", 0, "invalid_route");
  }
  return route;
}

export type QueryValue = string | number | boolean | null | undefined;

export function queryPath(
  path: string,
  values: Record<string, QueryValue>,
): string {
  const [pathname, current = ""] = path.split("?");
  const params = new URLSearchParams(current);
  Object.entries(values).forEach(([key, value]) => {
    if (value == null || value === "") params.delete(key);
    else params.set(key, String(value));
  });
  const query = params.toString();
  return query ? pathname + "?" + query : pathname;
}

export interface ApiFetchOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  csrfToken?: string | null;
  signal?: AbortSignal;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isAbort(error: unknown): boolean {
  return isRecord(error) && error.name === "AbortError";
}

export async function apiFetch<T = unknown>(
  path: string,
  options: ApiFetchOptions = {},
): Promise<T> {
  const method = options.method ?? "GET";
  const write = method !== "GET";
  if (write && !options.csrfToken)
    throw new ApiError(
      "Sign in again before saving changes.",
      403,
      "csrf_missing",
    );
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (write) headers["X-CSRFToken"] = options.csrfToken!;
  let response: Response;
  try {
    response = await fetch(apiPath(path), {
      method,
      credentials: "same-origin",
      mode: "same-origin",
      cache: "no-store",
      redirect: "error",
      headers,
      body:
        options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
    });
  } catch (error) {
    if (isAbort(error) || error instanceof ApiError) throw error;
    throw new ApiError("Cannot reach IZ2. Check the server and try again.");
  }
  if (response.status === 204) return undefined as T;
  const contentType = response.headers.get("content-type") ?? "";
  if (
    !contentType.includes("application/json") &&
    !contentType.includes("+json")
  ) {
    throw new ApiError(
      "The server returned an unexpected response. Try again.",
      response.status,
      "invalid_response",
    );
  }
  let value: unknown;
  try {
    value = await response.json();
  } catch (error) {
    if (isAbort(error)) throw error;
    throw new ApiError(
      "The server response could not be read. Try again.",
      response.status,
      "invalid_response",
    );
  }
  if (!response.ok) {
    const envelope =
      isRecord(value) && isRecord(value.error) ? value.error : null;
    throw new ApiError(
      envelope && typeof envelope.message === "string"
        ? envelope.message
        : "The request could not be completed.",
      response.status,
      envelope && typeof envelope.code === "string"
        ? envelope.code
        : "request_failed",
      envelope?.details ?? null,
    );
  }
  return value as T;
}

export function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  return apiFetch<T>(path, { signal });
}

export interface ApiState<T> {
  data: T | null;
  loading: boolean;
  error: ApiError | null;
  reload: () => void;
}

/** Cancel superseded reads and never let an old route replace the current result. */
export function useApi<T>(path: string | null): ApiState<T> {
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState<{
    path: string | null;
    data: T | null;
    loading: boolean;
    error: ApiError | null;
  }>({ path, data: null, loading: path !== null, error: null });
  const reload = useCallback(() => setRevision((value) => value + 1), []);
  useEffect(() => {
    if (path === null) {
      setState({ path, data: null, loading: false, error: null });
      return;
    }
    const controller = new AbortController();
    let active = true;
    setState((previous) => ({
      path,
      data: previous.path === path ? previous.data : null,
      loading: true,
      error: null,
    }));
    getJson<T>(path, controller.signal)
      .then((data) => {
        if (active) setState({ path, data, loading: false, error: null });
      })
      .catch((error) => {
        if (!active || isAbort(error)) return;
        setState((previous) => ({
          path,
          data: previous.path === path ? previous.data : null,
          loading: false,
          error:
            error instanceof ApiError
              ? error
              : new ApiError("The saved data could not be loaded."),
        }));
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [path, revision]);
  const current =
    state.path === path
      ? state
      : { path, data: null, loading: path !== null, error: null };
  return {
    data: current.data,
    loading: current.loading,
    error: current.error,
    reload,
  };
}
