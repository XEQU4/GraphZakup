import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ClusterDetail } from "./ClusterDetail";
import type {
  AnalysisResponse,
  AnalysisSnapshot,
  Cluster,
  Explanation,
  GraphResponse,
  GraphSnapshot,
} from "../lib/types";

const authority = vi.hoisted(() => ({ staff: false }));
vi.mock("../components/Session", () => ({
  useSession: () => ({
    capabilities: { can_start_jobs: authority.staff },
    csrfToken: "synthetic-csrf",
  }),
}));
vi.mock("../components/GraphExplorer", () => ({
  GraphExplorer: ({ graph }: { graph: GraphResponse }) => (
    <div>Rendered saved graph v{graph.version}</div>
  ),
  safeGraphLink: (value: string) => (value.startsWith("https:") ? value : null),
}));
const uuid = "synthetic-group";
const snapshot = (version: number): GraphSnapshot => ({
  id: version,
  version,
  graph_hash: "a".repeat(64),
  algorithm_version: "test",
  state: "active",
  as_of: "2026-10-07",
  member_ids: [1],
  changes: {},
  previous_id: version === 1 ? null : 1,
  created_at: "2026-10-07T10:00:00Z",
});
const cluster: Cluster = {
  uuid,
  name: "Synthetic saved group",
  is_active: true,
  review_priority: 2,
  company_count: 1,
  current_snapshot: snapshot(2),
  created_at: "2026-10-07T10:00:00Z",
  updated_at: "2026-10-07T10:00:00Z",
};
const graph = (version: number): GraphResponse => ({
  cluster: uuid,
  version,
  snapshot_id: version,
  graph_hash: "a".repeat(64),
  state: "active",
  historical: version === 1,
  graph: {
    nodes: [
      {
        id: "company:1",
        kind: "company",
        name: "Synthetic Company",
        company_id: 1,
        bin: "000000000001",
      },
    ],
    links: [],
  },
});
const analysis = (version: number): AnalysisSnapshot => ({
  id: version,
  version,
  graph_snapshot_id: version,
  graph_version: version,
  analysis_hash: "b".repeat(64),
  rules_version: "review-rules-5.0",
  as_of: "2026-10-07",
  created_at: "2026-10-07T10:00:00Z",
  findings: [],
  limitations: [],
  metrics: {
    review_priority: 2,
    relationship_priority: 2,
    financial_priority: 0,
    link_strength: 20,
    behavioural_risk: null,
    behavioural_status: "not_assessable",
    company_count: 1,
    fresh_arrears_checks: 0,
    unknown_current_arrears: 1,
    retained_recent_arrears_results: 0,
    companies_with_fresh_arrears: [],
    score_interpretation: "uncalibrated_review_priority",
    stored_contract_count: 0,
    stored_contract_amount: "0.00",
    shared_customer_count: 0,
    score_categories: {},
    score_breakdown: [],
  },
});
const explanation = (version: number): Explanation => ({
  id: version,
  analysis_id: version,
  text:
    version === 1
      ? "Original immutable explanation.\n\nOriginal evidence remains unchanged."
      : "Current saved explanation.",
  language: "en",
  provider: "template",
  model: "",
  prompt_version: "5.0",
  status: "ready",
  created_at: "2026-10-07T10:00:00Z",
  document: null,
});
const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { "content-type": "application/json" },
  });
const paginated = <T,>(results: T[]) => ({
  count: results.length,
  results,
  next: null,
  previous: null,
});
let fetcher: ReturnType<typeof vi.fn>;

beforeEach(() => {
  authority.staff = false;
  fetcher = vi.fn().mockImplementation((href: string) => {
    const url = new URL(href, "http://localhost");
    const pathname = url.pathname;
    if (pathname === `/api/v1/clusters/${uuid}/`)
      return Promise.resolve(json(cluster));
    if (pathname.endsWith("/snapshots/"))
      return Promise.resolve(json(paginated([snapshot(2), snapshot(1)])));
    if (pathname.endsWith("/graph/"))
      return Promise.resolve(
        json(graph(Number(url.searchParams.get("version")) || 2)),
      );
    if (pathname.endsWith("/analysis/")) {
      const version = Number(url.searchParams.get("version"));
      const response: AnalysisResponse = {
        cluster: uuid,
        graph_version: version,
        status: "ready",
        historical: version === 1,
        analysis: analysis(version),
        explanation: explanation(version),
      };
      return Promise.resolve(json(response));
    }
    if (pathname.endsWith("/analyses/"))
      return Promise.resolve(json(paginated([analysis(2), analysis(1)])));
    if (pathname.endsWith("/explanations/"))
      return Promise.resolve(
        json(
          paginated([explanation(pathname.includes("/analyses/1/") ? 1 : 2)]),
        ),
      );
    if (pathname.endsWith("/explanations/1/"))
      return Promise.resolve(json(explanation(1)));
    if (pathname.endsWith("/evidence/"))
      return Promise.resolve(json(paginated([])));
    const detailVersion = pathname.match(/\/snapshots\/(\d+)\//)?.[1];
    if (detailVersion)
      return Promise.resolve(
        json({
          ...snapshot(Number(detailVersion)),
          cluster: uuid,
          graph: graph(Number(detailVersion)).graph,
          incoming_transitions: [],
          outgoing_transitions: [],
        }),
      );
    return Promise.resolve(
      json({ error: { code: "not_found", message: "Not found." } }, 404),
    );
  });
  vi.stubGlobal("fetch", fetcher);
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("immutable cluster reads", () => {
  it("opens the selected historical graph and its exact analysis without generating anything", async () => {
    render(
      <MemoryRouter initialEntries={[`/clusters/${uuid}?version=1`]}>
        <Routes>
          <Route path="/clusters/:uuid" element={<ClusterDetail />} />
        </Routes>
      </MemoryRouter>,
    );
    await screen.findByText("Original immutable explanation.");
    expect(
      screen.getByText("Original evidence remains unchanged."),
    ).toBeInTheDocument();
    expect(screen.getByText("Rendered saved graph v1")).toBeInTheDocument();
    expect(screen.getByText("Historical saved version")).toBeInTheDocument();
    expect(
      fetcher.mock.calls.some((call) =>
        String(call[0]).includes("/analysis/?version=1"),
      ),
    ).toBe(true);
    expect(fetcher.mock.calls.every((call) => call[1].method === "GET")).toBe(
      true,
    );
    expect(
      fetcher.mock.calls.some(
        (call) =>
          /recalculate|\/explanations\/$/.test(String(call[0])) &&
          call[1].method !== "GET",
      ),
    ).toBe(false);
    expect(screen.queryByText("Staff actions")).not.toBeInTheDocument();
  });

  it("switches to current saved results and keeps history selection scoped to its graph", async () => {
    render(
      <MemoryRouter
        initialEntries={[
          `/clusters/${uuid}?version=1&analysis_version=1&explanation=1`,
        ]}
      >
        <Routes>
          <Route path="/clusters/:uuid" element={<ClusterDetail />} />
        </Routes>
      </MemoryRouter>,
    );
    await screen.findByText("Original immutable explanation.");
    fireEvent.change(screen.getByLabelText("Graph version"), {
      target: { value: "" },
    });
    await screen.findByText("Current saved explanation.");
    expect(
      screen.queryByText("Original immutable explanation."),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Rendered saved graph v2")).toBeInTheDocument();
    expect(screen.getByLabelText("Analysis version")).toHaveValue("");
    expect(screen.getByLabelText("Explanation history")).toHaveValue("");
    await waitFor(() =>
      expect(
        fetcher.mock.calls.some(
          (call) =>
            String(call[0]).includes("/analysis/?version=2") &&
            !String(call[0]).includes("analysis_version="),
        ),
      ).toBe(true),
    );
    expect(fetcher.mock.calls.every((call) => call[1].method === "GET")).toBe(
      true,
    );
  });

  it("opens snapshot-scoped evidence as a readable dialog and never navigates to raw JSON", async () => {
    const existing = fetcher.getMockImplementation() as (
      href: string,
      options: unknown,
    ) => Promise<Response>;
    fetcher.mockImplementation((href: string, options: unknown) => {
      if (href.includes("/evidence/observation%3A9/"))
        return Promise.resolve(
          json({
            id: "observation:9",
            kind: "observation",
            graph_snapshot_id: 2,
            source: "Synthetic source",
            quality: "confirmed",
            observed_at: "2026-10-07T10:00:00Z",
            parser_version: "1.0",
            status: "success",
          }),
        );
      if (href.includes("/evidence/?"))
        return Promise.resolve(
          json(
            paginated([
              {
                id: "observation:9",
                kind: "observation",
                graph_snapshot_id: 2,
                source: "Synthetic source",
                quality: "confirmed",
              },
            ]),
          ),
        );
      return existing(href, options);
    });
    render(
      <MemoryRouter initialEntries={[`/clusters/${uuid}`]}>
        <Routes>
          <Route path="/clusters/:uuid" element={<ClusterDetail />} />
        </Routes>
      </MemoryRouter>,
    );
    await screen.findByRole("button", {
      name: "Inspect saved evidence observation:9",
    });
    expect(
      fetcher.mock.calls.some((call) =>
        String(call[0]).includes("observation%3A9"),
      ),
    ).toBe(false);
    const opener = screen.getByRole("button", {
      name: "Inspect saved evidence observation:9",
    });
    opener.focus();
    fireEvent.click(opener);
    await screen.findByRole("dialog", { name: "Saved evidence record" });
    await screen.findByText("Source status");
    expect(screen.getByText("success")).toBeInTheDocument();
    expect(
      fetcher.mock.calls.some(
        (call) =>
          String(call[0]) === "/api/v1/snapshots/2/evidence/observation%3A9/",
      ),
    ).toBe(true);
    fireEvent.click(
      screen.getByRole("button", { name: "Close saved evidence" }),
    );
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
    await waitFor(() => expect(opener).toHaveFocus());
  });

  it("starts a template job only after the explicit staff action and cancels its polling on unmount", async () => {
    authority.staff = true;
    const existing = fetcher.getMockImplementation() as (
      href: string,
      options: unknown,
    ) => Promise<Response>;
    fetcher.mockImplementation((href: string, options: { method: string }) =>
      options.method === "POST"
        ? Promise.resolve(
            json(
              {
                job: "synthetic-job",
                kind: "analysis",
                status: "pending",
                error_code: "",
                created: true,
                created_at: "2026-10-07T10:00:00Z",
                finished_at: null,
              },
              202,
            ),
          )
        : existing(href, options),
    );
    const { unmount } = render(
      <MemoryRouter initialEntries={[`/clusters/${uuid}`]}>
        <Routes>
          <Route path="/clusters/:uuid" element={<ClusterDetail />} />
        </Routes>
      </MemoryRouter>,
    );
    await screen.findByText("Current saved explanation.");
    expect(fetcher.mock.calls.every((call) => call[1].method === "GET")).toBe(
      true,
    );
    fireEvent.click(screen.getByText("Staff actions"));
    fireEvent.click(
      screen.getByRole("button", { name: "Prepare template explanation" }),
    );
    expect(fetcher.mock.calls.every((call) => call[1].method === "GET")).toBe(
      true,
    );
    vi.useFakeTimers();
    await act(async () => {
      fireEvent.click(
        screen.getByRole("button", { name: "Start background task" }),
      );
    });
    const writes = fetcher.mock.calls.filter(
      (call) => call[1].method === "POST",
    );
    expect(writes).toHaveLength(1);
    expect(writes[0][0]).toBe(`/api/v1/clusters/${uuid}/explanations/`);
    expect(JSON.parse(writes[0][1].body)).toEqual({
      use_model: false,
      retry_model: false,
    });
    const count = fetcher.mock.calls.length;
    unmount();
    await act(async () => {
      vi.advanceTimersByTime(10000);
    });
    expect(fetcher).toHaveBeenCalledTimes(count);
  });
});
