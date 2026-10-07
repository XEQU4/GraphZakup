import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiFetch, apiPath, getJson, queryPath, useApi } from "./api";
import { formatDate, formatMoney, safeHttpUrl } from "./utils";

function json(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("same-origin API boundary", () => {
  it("accepts only project API routes and rejects decoded traversal", () => {
    expect(apiPath("companies/?page=2")).toBe("/api/v1/companies/?page=2");
    expect(apiPath("/api/v1/clusters/")).toBe("/api/v1/clusters/");
    for (const value of [
      "https://elsewhere.example/api",
      "//elsewhere.example/api",
      "/admin/",
      "../session/",
      "companies/../../admin/",
      "%2e%2e/admin/",
      "%252e%252e/admin/",
      "companies/%5cadmin/",
      "companies/#x",
      "companies/ a",
      "companies/%zz",
    ]) {
      expect(() => apiPath(value)).toThrow(ApiError);
    }
  });

  it("encodes filters and retains intentional false/zero values", () => {
    expect(
      queryPath("companies/?page=9", {
        page: 1,
        search: "A & B",
        is_supplier: false,
        minimum: 0,
        absent: null,
      }),
    ).toBe("companies/?page=1&search=A+%26+B&is_supplier=false&minimum=0");
    expect(queryPath("companies/?search=old&page=2", { search: "" })).toBe(
      "companies/?page=2",
    );
  });

  it("sends cookies only to the same origin, rejects redirects, and disables HTTP caching", async () => {
    const fetcher = vi.fn().mockResolvedValue(json({ count: 0, results: [] }));
    vi.stubGlobal("fetch", fetcher);
    await getJson("companies/");
    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/companies/",
      expect.objectContaining({
        method: "GET",
        credentials: "same-origin",
        mode: "same-origin",
        cache: "no-store",
        redirect: "error",
        headers: { Accept: "application/json" },
      }),
    );
  });

  it("requires a CSRF token before any write and does not send credentials to another site", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    await expect(
      apiFetch("session/login/", {
        method: "POST",
        body: { username: "demo", password: "secret" },
      }),
    ).rejects.toMatchObject({ status: 403, code: "csrf_missing" });
    await expect(
      apiFetch("https://elsewhere.example/", {
        method: "POST",
        body: { password: "secret" },
        csrfToken: "csrf",
      }),
    ).rejects.toMatchObject({ code: "invalid_route" });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("serializes JSON and sends only the supplied rotated CSRF token", async () => {
    const fetcher = vi.fn().mockResolvedValue(json({ revision: 2 }));
    vi.stubGlobal("fetch", fetcher);
    await apiFetch("clusters/fixture/view/", {
      method: "PUT",
      csrfToken: "rotated-token",
      body: { revision: 1 },
    });
    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/clusters/fixture/view/",
      expect.objectContaining({
        body: '{"revision":1}',
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": "rotated-token",
        },
      }),
    );
  });

  it("preserves structured conflicts and error details for callers", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        json(
          {
            error: {
              code: "view_conflict",
              message: "Reload before saving.",
              details: { revision: 4 },
            },
          },
          409,
        ),
      ),
    );
    await expect(getJson("clusters/fixture/view/")).rejects.toMatchObject({
      status: 409,
      code: "view_conflict",
      message: "Reload before saving.",
      details: { revision: 4 },
    });
  });

  it("handles non-JSON server errors without exposing returned HTML", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("<h1>private traceback</h1>", {
          status: 500,
          headers: { "content-type": "text/html" },
        }),
      ),
    );
    await expect(getJson("companies/")).rejects.toMatchObject({
      status: 500,
      code: "invalid_response",
    });
    try {
      await getJson("companies/");
    } catch (value) {
      expect((value as Error).message).not.toContain("traceback");
    }
  });

  it("handles malformed JSON, network failures and an empty logout response", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        new Response("{", { headers: { "content-type": "application/json" } }),
      )
      .mockRejectedValueOnce(new TypeError("fetch failed"))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetcher);
    await expect(getJson("companies/")).rejects.toMatchObject({
      code: "invalid_response",
    });
    await expect(getJson("companies/")).rejects.toMatchObject({
      code: "network_error",
      status: 0,
    });
    await expect(
      apiFetch("session/logout/", { method: "POST", csrfToken: "csrf" }),
    ).resolves.toBeUndefined();
  });

  it("propagates cancellation instead of showing a network error", async () => {
    const abort = new DOMException("Aborted", "AbortError");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(abort));
    await expect(getJson("companies/")).rejects.toBe(abort);
  });
});

describe("saved-data hook", () => {
  it("cancels an old route and ignores a late response even if the transport ignores abort", async () => {
    const old = deferred<Response>();
    const latest = deferred<Response>();
    const fetcher = vi
      .fn()
      .mockReturnValueOnce(old.promise)
      .mockReturnValueOnce(latest.promise);
    vi.stubGlobal("fetch", fetcher);
    const { result, rerender } = renderHook(
      ({ path }) => useApi<{ name: string }>(path),
      { initialProps: { path: "companies/1/" } },
    );
    const oldSignal = fetcher.mock.calls[0][1].signal as AbortSignal;
    rerender({ path: "companies/2/" });
    expect(oldSignal.aborted).toBe(true);
    expect(result.current.data).toBeNull();
    await act(async () => {
      latest.resolve(json({ name: "Current company" }));
    });
    await waitFor(() =>
      expect(result.current.data?.name).toBe("Current company"),
    );
    await act(async () => {
      old.resolve(json({ name: "Old company" }));
    });
    expect(result.current.data?.name).toBe("Current company");
    expect(result.current.error).toBeNull();
  });

  it("makes no request for a null path, retries explicitly, and aborts on unmount", async () => {
    const pending = deferred<Response>();
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        json({ error: { code: "unavailable", message: "Try again." } }, 503),
      )
      .mockReturnValueOnce(pending.promise);
    vi.stubGlobal("fetch", fetcher);
    const { result, rerender, unmount } = renderHook(
      ({ path }) => useApi<{ value: number }>(path),
      { initialProps: { path: null as string | null } },
    );
    expect(fetcher).not.toHaveBeenCalled();
    expect(result.current.loading).toBe(false);
    rerender({ path: "companies/" });
    await waitFor(() => expect(result.current.error?.status).toBe(503));
    act(() => result.current.reload());
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
    const signal = fetcher.mock.calls[1][1].signal as AbortSignal;
    unmount();
    expect(signal.aborted).toBe(true);
    await act(async () => {
      pending.resolve(json({ value: 5 }));
    });
  });
});

describe("source display", () => {
  it("retains every digit of large decimal amounts and distinguishes missing money from zero", () => {
    expect(formatMoney("999999999999999999.99")).toBe(
      "999,999,999,999,999,999.99 KZT",
    );
    expect(formatMoney("0.00")).toBe("0.00 KZT");
    expect(formatMoney("-1000000.25")).toBe("-1,000,000.25 KZT");
    expect(formatMoney(null)).toBe("Not available");
    expect(formatMoney("NaN")).toBe("Not available");
    expect(formatMoney("000012.1")).toBe("12.10 KZT");
    expect(formatMoney("1.125")).toBe("1.125 KZT");
  });

  it("keeps date-only records on their source day and rejects impossible dates", () => {
    expect(formatDate("2026-10-07")).toBe("07 Oct 2026");
    expect(formatDate("2026-02-31")).toBe("Not recorded");
    expect(formatDate("bad")).toBe("Not recorded");
    expect(formatDate(null)).toBe("Not recorded");
  });

  it("only makes explicit safe HTTP(S) source references navigable", () => {
    expect(safeHttpUrl("https://example.gov.kz/record/42")).toBe(
      "https://example.gov.kz/record/42",
    );
    for (const value of [
      "javascript:alert(1)",
      "data:text/html,hi",
      "//example.gov.kz",
      "https://user:password@example.gov.kz/",
      "https://example.gov.kz/\\evil",
      "https://example.gov.kz/" + String.fromCharCode(10) + "foo",
      "/local/path",
      "",
    ])
      expect(safeHttpUrl(value)).toBeNull();
  });
});
