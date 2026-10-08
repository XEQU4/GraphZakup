import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  MemoryRouter,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { Clusters } from "./Clusters";
import type { Cluster, ClusterDirectory } from "../lib/types";

const savedDirectory: ClusterDirectory = {
  title: "Shared phone · 5 companies",
  companies: [
    { id: 1, name: "Synthetic <North> Services", bin: "000000000001" },
    { id: 2, name: "Synthetic Riverstone", bin: "000000000002" },
    { id: 3, name: "Synthetic Steppe", bin: "000000000003" },
  ],
  additional_companies: 2,
  reasons: [{ type: "phone", label: "Shared phone", company_count: 5 }],
  primary_reason: { type: "phone", label: "Shared phone", company_count: 5 },
  analysis_status: "ready",
  analysis_as_of: "2026-10-08",
  review_priority: 5,
  coverage: { status: "no_checks", checked: 0, total: 5, as_of: "2026-10-08" },
};
const cluster: Cluster = {
  uuid: "synthetic-group",
  name: "Legacy name and 4 more",
  is_active: true,
  review_priority: 99,
  company_count: 5,
  current_snapshot: {
    id: 3,
    version: 3,
    graph_hash: "a".repeat(64),
    algorithm_version: "synthetic",
    state: "active",
    as_of: "2026-10-07",
    member_ids: [1, 2, 3, 4, 5],
    changes: {},
    previous_id: 2,
    created_at: "2026-10-07T00:00:00Z",
  },
  created_at: "2026-10-07T00:00:00Z",
  updated_at: "2026-10-08T00:00:00Z",
  directory: savedDirectory,
};
let reads: URL[];
let response: (url: URL) => Response;
function json(results: Cluster[], count = results.length) {
  return new Response(
    JSON.stringify({ count, results, next: null, previous: null }),
    { headers: { "content-type": "application/json" } },
  );
}
function Navigation() {
  const navigate = useNavigate();
  const location = useLocation();
  return (
    <>
      <button type="button" onClick={() => navigate(-1)}>
        Browser back
      </button>
      <output data-testid="location">
        {location.pathname}
        {location.search}
      </output>
      <output data-testid="route-state">
        {JSON.stringify(location.state)}
      </output>
    </>
  );
}
function show(path = "/clusters") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Navigation />
      <Routes>
        <Route path="/clusters" element={<Clusters />} />
        <Route path="/clusters/:uuid" element={<p>Saved detail route</p>} />
      </Routes>
    </MemoryRouter>,
  );
}
beforeEach(() => {
  reads = [];
  response = () => json([cluster]);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string, init?: RequestInit) => {
      expect(init?.method ?? "GET").toBe("GET");
      const url = new URL(input, "http://localhost");
      reads.push(url);
      return response(url);
    }),
  );
});
afterEach(() => vi.unstubAllGlobals());
async function cards() {
  return screen.findByRole("region", { name: "Relationship group results" });
}

describe("relationship group directory", () => {
  it("shows the prepared reason, escaped frozen names and exact saved metrics with one list read", async () => {
    show();
    const results = await cards();
    expect(
      within(results).getByRole("heading", {
        name: "Shared phone · 5 companies",
      }),
    ).toBeInTheDocument();
    expect(
      within(results).getByText(
        "5 company records have shared phone connections.",
      ),
    ).toBeInTheDocument();
    expect(
      within(results).getByText("Synthetic <North> Services"),
    ).toBeInTheDocument();
    expect(results.querySelector("north")).toBeNull();
    expect(within(results).getByText("+ 2 more companies")).toBeInTheDocument();
    expect(
      results.querySelector(".group-card-priority")?.textContent,
    ).toContain("5/100");
    expect(
      results.querySelector(".group-card-priority")?.textContent,
    ).not.toContain("99");
    expect(
      within(results).getByText("No usable checks at this date"),
    ).toBeInTheDocument();
    expect(
      within(results).getByText("At analysis date · 08 Oct 2026"),
    ).toBeInTheDocument();
    expect(
      within(results).getByText("Evidence · 07 Oct 2026"),
    ).toBeInTheDocument();
    expect(within(results).getByRole("link")).toHaveAttribute(
      "href",
      "/clusters/synthetic-group",
    );
    expect(reads).toHaveLength(1);
    expect(reads[0].pathname).toBe("/api/v1/clusters/");
  });
  it("keeps unknown analysis separate from a genuine saved zero", async () => {
    response = () =>
      json([
        {
          ...cluster,
          directory: {
            ...savedDirectory,
            analysis_status: "not_calculated",
            review_priority: null,
            coverage: {
              status: "not_assessed",
              checked: null,
              total: 5,
              as_of: null,
            },
          },
        },
      ]);
    show();
    const results = await cards();
    expect(within(results).getByText("Not calculated")).toBeInTheDocument();
    expect(within(results).getByText("Not assessed")).toBeInTheDocument();
    expect(results.querySelector(".group-card-priority-track")).toBeNull();
    expect(results.textContent).not.toContain("0/100");
    response = () =>
      json([
        { ...cluster, directory: { ...savedDirectory, review_priority: 0 } },
      ]);
    fireEvent.change(screen.getByRole("combobox", { name: "Connection" }), {
      target: { value: "phone" },
    });
    await waitFor(() =>
      expect(
        screen
          .getByRole("region", { name: "Relationship group results" })
          .querySelector(".group-card-priority")?.textContent,
      ).toContain("0/100"),
    );
  });
  it("labels earlier analysis and never substitutes the legacy score for missing matching data", async () => {
    response = () =>
      json([
        {
          ...cluster,
          directory: {
            ...savedDirectory,
            analysis_status: "stale",
            review_priority: null,
            coverage: {
              status: "not_assessed",
              checked: null,
              total: 5,
              as_of: null,
            },
          },
        },
      ]);
    show();
    const results = await cards();
    expect(within(results).getByText("Earlier analysis")).toBeInTheDocument();
    expect(within(results).getByText("Not calculated")).toBeInTheDocument();
    expect(results.textContent).not.toContain("99/100");
    expect(
      within(results).getByText("No saved coverage available"),
    ).toBeInTheDocument();
  });
  it("describes dated usable KGD checks without claiming complete current data or no debt", async () => {
    response = () =>
      json([
        {
          ...cluster,
          directory: {
            ...savedDirectory,
            coverage: {
              status: "checked",
              checked: 5,
              total: 5,
              as_of: "2026-10-01",
            },
          },
        },
      ]);
    show();
    const results = await cards();
    expect(
      within(results).getByText("Usable checks at this date"),
    ).toBeInTheDocument();
    expect(
      within(results).getByText("At analysis date · 01 Oct 2026"),
    ).toBeInTheDocument();
    expect(results.textContent).not.toMatch(
      /complete data|debt.free|no debt|100%/i,
    );
  });
  it("trims search, resets the page and removes only the selected filter", async () => {
    show("/clusters?relationship=phone&coverage=no_checks&page=2");
    await cards();
    expect(reads[0].searchParams.get("page")).toBe("2");
    const search = screen.getByRole("searchbox");
    fireEvent.change(search, { target: { value: " 000000000002 " } });
    fireEvent.submit(search.closest("form")!);
    await waitFor(() => {
      expect(reads.at(-1)?.searchParams.get("search")).toBe("000000000002");
      expect(reads.at(-1)?.searchParams.get("page")).toBe("1");
      expect(reads.at(-1)?.searchParams.get("coverage")).toBe("no_checks");
    });
    expect(search).toHaveValue("000000000002");
    fireEvent.click(
      screen.getByRole("button", { name: "Remove Shared phone" }),
    );
    await waitFor(() => {
      expect(reads.at(-1)?.searchParams.has("relationship")).toBe(false);
      expect(reads.at(-1)?.searchParams.get("search")).toBe("000000000002");
      expect(reads.at(-1)?.searchParams.get("coverage")).toBe("no_checks");
    });
  });
  it("restores filters on browser back and carries the directory query into the native card link", async () => {
    show("/clusters?search=Riverstone&relationship=phone&page=2");
    await cards();
    fireEvent.change(
      screen.getByRole("combobox", { name: "Saved KGD coverage" }),
      { target: { value: "partial" } },
    );
    await waitFor(() =>
      expect(reads.at(-1)?.searchParams.get("coverage")).toBe("partial"),
    );
    fireEvent.click(screen.getByRole("button", { name: "Browser back" }));
    await waitFor(() => {
      expect(
        screen.getByRole("combobox", { name: "Saved KGD coverage" }),
      ).toHaveValue("");
      expect(reads.at(-1)?.searchParams.get("page")).toBe("2");
    });
    expect(screen.getByRole("searchbox")).toHaveValue("Riverstone");
    fireEvent.click(within(await cards()).getByRole("link"));
    expect(await screen.findByText("Saved detail route")).toBeInTheDocument();
    expect(
      JSON.parse(screen.getByTestId("route-state").textContent ?? "{}"),
    ).toEqual({
      directorySearch: "search=Riverstone&relationship=phone&page=2",
    });
  });
  it("combines archived, priority and sort filters and resets to the active directory", async () => {
    show(
      "/clusters?minimum_review_priority=25&ordering=name&search=Riverstone",
    );
    await cards();
    expect(reads[0].searchParams.get("minimum_review_priority")).toBe("25");
    expect(
      screen.getByRole("option", { name: "Saved group name" }),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Group state" }), {
      target: { value: "false" },
    });
    await waitFor(() =>
      expect(reads.at(-1)?.searchParams.get("active")).toBe("false"),
    );
    fireEvent.click(screen.getByRole("button", { name: "Reset filters" }));
    await waitFor(() => {
      expect(reads.at(-1)?.searchParams.get("active")).toBe("true");
      expect(reads.at(-1)?.searchParams.get("ordering")).toBe(
        "-review_priority",
      );
      expect(reads.at(-1)?.searchParams.has("minimum_review_priority")).toBe(
        false,
      );
    });
    expect(screen.getByRole("searchbox")).toHaveValue("");
    expect(screen.getByTestId("location")).toHaveTextContent(/^\/clusters$/);
  });
  it("distinguishes an empty saved directory from no filter matches", async () => {
    response = () => json([]);
    show();
    expect(
      await screen.findByText("No active relationship groups saved"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("region", { name: "Relationship group results" }),
    ).toBeNull();
    fireEvent.change(screen.getByRole("combobox", { name: "Connection" }), {
      target: { value: "owner" },
    });
    expect(
      await screen.findByText("No groups match these filters"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("No active relationship groups saved"),
    ).toBeNull();
  });
  it("retries a failed read instead of reporting no groups", async () => {
    response = () =>
      new Response(
        JSON.stringify({
          error: {
            message: "Synthetic temporary failure",
            code: "unavailable",
          },
        }),
        { status: 503, headers: { "content-type": "application/json" } },
      );
    show();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Synthetic temporary failure",
    );
    expect(
      screen.queryByText("No active relationship groups saved"),
    ).toBeNull();
    response = () => json([cluster]);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await cards();
    expect(reads).toHaveLength(2);
  });
  it("preserves filters across pagination and recovers an out-of-range page", async () => {
    response = () => json([cluster], 25);
    show("/clusters?relationship=phone&coverage=no_checks");
    await cards();
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    await waitFor(() => {
      expect(reads.at(-1)?.searchParams.get("page")).toBe("2");
      expect(reads.at(-1)?.searchParams.get("relationship")).toBe("phone");
      expect(reads.at(-1)?.searchParams.get("coverage")).toBe("no_checks");
    });
    await cards();
    response = () =>
      new Response(
        JSON.stringify({
          error: { message: "Invalid page.", code: "not_found" },
        }),
        { status: 404, headers: { "content-type": "application/json" } },
      );
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    const recover = await screen.findByRole("button", {
      name: "Return to first page",
    });
    response = () => json([cluster]);
    fireEvent.click(recover);
    await waitFor(() =>
      expect(reads.at(-1)?.searchParams.get("page")).toBe("1"),
    );
    await cards();
  });
  it("keeps old responses readable and supports mixed-role reasons without a false shared-owner claim", async () => {
    response = () => json([{ ...cluster, directory: undefined }]);
    show();
    let results = await cards();
    expect(
      within(results).getByRole("heading", { name: "Legacy name and 4 more" }),
    ).toBeInTheDocument();
    expect(
      within(results).getByText(
        "Open the saved graph to inspect its connections.",
      ),
    ).toBeInTheDocument();
    expect(results.textContent).not.toContain("99/100");
    response = () =>
      json([
        {
          ...cluster,
          directory: {
            ...savedDirectory,
            title: "Shared person across roles · 5 companies",
            primary_reason: {
              type: "mixed_roles",
              label: "Shared person across roles",
              company_count: 5,
            },
          },
        },
      ]);
    fireEvent.change(screen.getByRole("combobox", { name: "Connection" }), {
      target: { value: "mixed_roles" },
    });
    expect(
      await screen.findByText(
        "5 company records connect through verified people in different roles.",
      ),
    ).toBeInTheDocument();
    results = await cards();
    expect(results.textContent).not.toContain("same owner");
  });
});
