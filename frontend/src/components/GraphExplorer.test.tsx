import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  adjacency,
  GraphExplorer,
  graphStorageKey,
  restorePositions,
  safeGraphLink,
  sanitizeView,
  shortestPath,
  wrappedLabel,
} from "./GraphExplorer";
import type {
  GraphEdge,
  GraphNode,
  GraphResponse,
  GraphView,
  ViewPayload,
} from "../lib/types";
import { MotionPreferences, useMotionPreferences } from "./MotionPreferences";
import { setLanguage } from "../i18n";

const state = vi.hoisted(() => ({
  user: {
    id: null as number | null,
    username: null as string | null,
    role: "anonymous" as "anonymous" | "user" | "staff",
  },
  csrfToken: "synthetic-csrf",
  loading: false,
}));
vi.mock("./Session", () => ({ useSession: () => state }));
const observer = vi.fn(),
  disconnect = vi.fn();
const nodes: GraphNode[] = [
  {
    id: "company:1",
    kind: "company",
    name: "Synthetic Company One",
    bin: "000000000001",
    company_id: 1,
  },
  {
    id: "company:2",
    kind: "company",
    name: "Synthetic Company Two",
    bin: "000000000002",
    company_id: 2,
  },
  {
    id: "contact:1",
    kind: "contact",
    name: "Synthetic office",
    contact_type: "address",
  },
];
const edge = (id: string, source: string, target: string): GraphEdge => ({
  id,
  source,
  target,
  type: "address",
  value: "Synthetic office",
  company_id: 1,
  confidence: "0.5",
  valid_from: null,
  valid_until: null,
  temporal_status: "unknown",
  evidence: [],
  limitations: [],
});
const graph: GraphResponse = {
  cluster: "synthetic-cluster",
  snapshot_id: 1,
  graph_hash: "a".repeat(64),
  version: 1,
  state: "active",
  historical: false,
  graph: {
    nodes,
    links: [
      edge("a", "company:1", "contact:1"),
      edge("b", "company:2", "contact:1"),
    ],
  },
};
const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { "content-type": "application/json" },
  });

beforeEach(() => {
  setLanguage("en");
  state.user = { id: null, username: null, role: "anonymous" };
  state.loading = false;
  localStorage.clear();
  observer.mockClear();
  disconnect.mockClear();
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe = observer;
      disconnect = disconnect;
    },
  );
});
afterEach(() => {
  cleanup();
  setLanguage("en");
  vi.unstubAllGlobals();
});

describe("graph relationship semantics", () => {
  it("keeps company paths distinct from direct edges and honours relationship filters", () => {
    const links = graph.graph.links.map((item) => ({ ...item }));
    expect(
      adjacency(nodes, links)
        .get("company:1")
        ?.map((item) => item.node),
    ).toEqual(["contact:1"]);
    expect(shortestPath(nodes, links, "company:1", "company:2")).toEqual({
      nodes: ["company:1", "contact:1", "company:2"],
      edges: ["a", "b"],
    });
    expect(
      shortestPath(nodes, links, "company:1", "company:2", ["director"]),
    ).toBeNull();
    expect(shortestPath(nodes, links, "missing", "company:2")).toBeNull();
  });

  it("preserves saved positions and places a new linked node without reusing an occupied position", () => {
    const restored = nodes.map((node) => ({
      ...node,
      x: 0,
      y: 0,
      pinned: false,
    }));
    restorePositions(restored, graph.graph.links, {
      positions: {
        "company:1": { x: 700, y: -400, pinned: true },
        "contact:1": { x: 900, y: -100, pinned: false },
      },
    });
    expect(restored[0]).toMatchObject({ x: 700, y: -400, pinned: true });
    expect(restored[2]).toMatchObject({ x: 900, y: -100, pinned: false });
    expect(
      Math.hypot(restored[1].x - 900, restored[1].y + 100),
    ).toBeGreaterThanOrEqual(250);
  });

  it("rejects corrupt browser view values and unsafe navigation without treating source values as HTML", () => {
    expect(graphStorageKey("id")).toBe("grafzakup.graph-view.v1.id");
    expect(sanitizeView([])).toBeNull();
    expect(
      sanitizeView({
        positions: {
          good: { x: 1, y: 2, pinned: true },
          infinite: { x: Infinity, y: 2 },
          coercion: { x: "3", y: 2 },
        },
        filters: ["address", "director", "address", "evil"],
        zoom: { x: 0, y: 0, k: 99 },
        selected: "company:1",
        frozen: true,
      }),
    ).toEqual({
      positions: { good: { x: 1, y: 2, pinned: true } },
      filters: ["address", "director"],
      selected: "company:1",
      frozen: true,
    });
    for (const href of [
      "javascript:alert(1)",
      "data:text/html,hi",
      "//evil.example",
      "https://user:password@example.org/",
      "/a\\b",
      "https://example.org/" + String.fromCharCode(10),
    ])
      expect(safeGraphLink(href)).toBeNull();
    expect(safeGraphLink("/app/companies/1")).toBe("/app/companies/1");
    expect(wrappedLabel("A".repeat(150), 24)).toHaveLength(3);
  });
});

describe("saved graph React lifecycle", () => {
  it("loads the original anonymous storage key, saves locally and stops observers on unmount", async () => {
    const payload = {
      positions: { "company:1": { x: 123, y: 456, pinned: true } },
      filters: ["address"],
      frozen: true,
    };
    localStorage.setItem(
      graphStorageKey(graph.cluster),
      JSON.stringify(payload),
    );
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    const { container, unmount } = render(<GraphExplorer graph={graph} />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save view" })).toBeEnabled(),
    );
    expect(
      container.querySelector(".graph-node")?.getAttribute("transform"),
    ).toBe("translate(123,456)");
    expect(screen.getByLabelText("Director")).not.toBeChecked();
    expect(screen.getByLabelText("Address")).toBeChecked();
    fireEvent.change(
      screen.getByPlaceholderText("Company, BIN, person or contact"),
      { target: { value: "000000000002" } },
    );
    expect(
      within(screen.getByLabelText("Matching nodes")).getByRole("button", {
        name: "company: Synthetic Company Two",
      }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save view" }));
    expect(
      JSON.parse(localStorage.getItem(graphStorageKey(graph.cluster))!),
    ).toMatchObject({
      positions: { "company:1": { x: 123, y: 456, pinned: true } },
      filters: ["address"],
      frozen: true,
    });
    expect(fetcher).not.toHaveBeenCalled();
    unmount();
    expect(disconnect).toHaveBeenCalledTimes(1);
  });

  it("uses authenticated PUT with the exact graph hash and fetched view revision; a conflict is visible", async () => {
    state.user = { id: 7, username: "synthetic-user", role: "user" };
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(json({ revision: 4, payload: { frozen: true } }))
      .mockResolvedValueOnce(
        json(
          {
            error: { code: "view_conflict", message: "Reload before saving." },
          },
          409,
        ),
      );
    vi.stubGlobal("fetch", fetcher);
    render(<GraphExplorer graph={graph} />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save view" })).toBeEnabled(),
    );
    expect(fetcher.mock.calls[0][0]).toBe(
      "/api/v1/clusters/synthetic-cluster/view/?version=1",
    );
    fireEvent.click(screen.getByRole("button", { name: "Save view" }));
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(
        "changed in another tab",
      ),
    );
    expect(fetcher.mock.calls[1][0]).toBe(
      "/api/v1/clusters/synthetic-cluster/view/",
    );
    expect(fetcher.mock.calls[1][1]).toMatchObject({
      method: "PUT",
      headers: { "X-CSRFToken": "synthetic-csrf" },
    });
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toMatchObject({
      snapshot_id: 1,
      graph_hash: "a".repeat(64),
      revision: 4,
    });
  });

  it("aborts a pending private view read and ignores its late result after unmount", async () => {
    state.user = { id: 7, username: "synthetic-user", role: "user" };
    let resolve!: (value: Response) => void;
    const fetcher = vi.fn().mockReturnValue(
      new Promise<Response>((yes) => {
        resolve = yes;
      }),
    );
    vi.stubGlobal("fetch", fetcher);
    const { unmount } = render(<GraphExplorer graph={graph} />);
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
    const signal = fetcher.mock.calls[0][1].signal as AbortSignal;
    unmount();
    expect(signal.aborted).toBe(true);
    resolve(json({ revision: 1, payload: {} }));
    await new Promise((yes) => setTimeout(yes, 5));
    expect(observer).not.toHaveBeenCalled();
  });

  it("keeps the new personal revision when an old canceled user read resolves late", async () => {
    state.user = { id: 7, username: "synthetic-first-user", role: "user" };
    let resolve!: (value: Response) => void;
    const old = new Promise<Response>((yes) => {
      resolve = yes;
    });
    const fetcher = vi
      .fn()
      .mockReturnValueOnce(old)
      .mockResolvedValueOnce(json({ revision: 9, payload: { frozen: true } }))
      .mockResolvedValueOnce(json({ revision: 10, payload: { frozen: true } }));
    vi.stubGlobal("fetch", fetcher);
    const { rerender } = render(<GraphExplorer graph={graph} />);
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
    state.user = { id: 8, username: "synthetic-current-user", role: "user" };
    rerender(<GraphExplorer graph={graph} />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save view" })).toBeEnabled(),
    );
    await act(async () => {
      resolve(json({ revision: 2, payload: { frozen: true } }));
    });
    fireEvent.click(screen.getByRole("button", { name: "Save view" }));
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(3));
    expect(JSON.parse(fetcher.mock.calls[2][1].body).revision).toBe(9);
  });

  it("uses the Vite route base for graph company navigation during development", async () => {
    render(<GraphExplorer graph={graph} />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Fit" })).toBeEnabled(),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "company: Synthetic Company One" }),
    );
    expect(screen.getByRole("link", { name: "Open company" })).toHaveAttribute(
      "href",
      "/companies/1",
    );
  });

  it("settles initial coordinates before Fit and keeps every node inside the viewport", async () => {
    vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(900);
    vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(650);
    const { container } = render(<GraphExplorer graph={graph} />);
    const layer = () => container.querySelector(".graph-canvas svg > g");
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Fit" })).toBeEnabled(),
    );
    await new Promise((resolve) => setTimeout(resolve, 340));
    await waitFor(() =>
      expect(layer()?.getAttribute("transform")).toMatch(/scale/),
    );
    const transform = layer()!
      .getAttribute("transform")!
      .match(/translate\(([^,]+),([^)]+)\) scale\(([^)]+)\)/)!;
    const tx = Number(transform[1]),
      ty = Number(transform[2]),
      scale = Number(transform[3]);
    const positions = Array.from(
      container.querySelectorAll(".graph-node"),
      (node) => node.getAttribute("transform"),
    );
    for (const position of positions) {
      const point = position!.match(/translate\(([^,]+),([^)]+)\)/)!;
      const x = Number(point[1]) * scale + tx,
        y = Number(point[2]) * scale + ty;
      expect(x - 125 * scale).toBeGreaterThanOrEqual(0);
      expect(x + 125 * scale).toBeLessThanOrEqual(900);
      expect(y - 105 * scale).toBeGreaterThanOrEqual(0);
      expect(y + 105 * scale).toBeLessThanOrEqual(650);
    }
    await new Promise((resolve) => setTimeout(resolve, 60));
    expect(
      Array.from(container.querySelectorAll(".graph-node"), (node) =>
        node.getAttribute("transform"),
      ),
    ).toEqual(positions);
  });

  it("does not create HTML from company names and disables historical view writes", async () => {
    const hostile = {
      ...graph,
      historical: true,
      graph: {
        ...graph.graph,
        nodes: [
          { ...nodes[0], name: "<img src=x onerror=alert(1)>" },
          ...nodes.slice(1),
        ],
      },
    };
    const { container } = render(<GraphExplorer graph={hostile} />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Fit" })).toBeEnabled(),
    );
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("title")?.textContent).toBe(
      "<img src=x onerror=alert(1)>",
    );
    expect(screen.getByRole("button", { name: "Save view" })).toBeDisabled();
  });
});

function MotionSwitch() {
  const { enabled, toggle } = useMotionPreferences();
  return (
    <button onClick={toggle}>
      {enabled ? "Pause graph motion" : "Enable graph motion"}
    </button>
  );
}

describe("graph presentation and motion", () => {
  it("keeps the same selected node and saved positions when motion is paused; camera and reveal timers stop", async () => {
    vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(900);
    vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(650);
    localStorage.setItem(
      graphStorageKey(graph.cluster),
      JSON.stringify({
        positions: {
          "company:1": { x: 100, y: 150, pinned: true },
          "company:2": { x: 450, y: 80, pinned: false },
          "contact:1": { x: 280, y: -180, pinned: false },
        },
        zoom: { x: 300, y: 300, k: 0.6 },
        frozen: true,
      }),
    );
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    const { container } = render(
      <MotionPreferences>
        <MotionSwitch />
        <GraphExplorer graph={graph} />
      </MotionPreferences>,
    );
    const canvas = container.querySelector(".graph-canvas")!;
    await waitFor(() =>
      expect(canvas).toHaveAttribute("data-motion-active", "true"),
    );
    const coordinates = () =>
      Array.from(container.querySelectorAll(".graph-node"), (node) =>
        node.getAttribute("transform"),
      );
    const before = coordinates();
    fireEvent.click(
      screen.getByRole("button", { name: "company: Synthetic Company One" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Focus this node" }));
    const svg = canvas.querySelector("svg")!;
    expect("__transition" in svg).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Pause graph motion" }));
    await waitFor(() =>
      expect(canvas).toHaveAttribute("data-motion-active", "false"),
    );
    expect("__transition" in svg).toBe(false);
    expect(
      Array.from(container.querySelectorAll(".graph-node")).some(
        (node) => "__transition" in node,
      ),
    ).toBe(false);
    expect(coordinates()).toEqual(before);
    expect(
      screen.getByRole("button", { name: "company: Synthetic Company One" }),
    ).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "Save view" }));
    expect(
      JSON.parse(localStorage.getItem(graphStorageKey(graph.cluster))!),
    ).toMatchObject({
      frozen: true,
      selected: "company:1",
      positions: { "company:1": { x: 100, y: 150, pinned: true } },
    });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("pauses when the document or graph is hidden, removes its observer, and retains keyboard evidence inspection", async () => {
    let notify!: IntersectionObserverCallback;
    const stop = vi.fn();
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        constructor(callback: IntersectionObserverCallback) {
          notify = callback;
        }
        observe(target: Element) {
          notify(
            [{ target, isIntersecting: true } as IntersectionObserverEntry],
            this as unknown as IntersectionObserver,
          );
        }
        disconnect = stop;
      },
    );
    const { container, unmount } = render(<GraphExplorer graph={graph} />);
    const canvas = container.querySelector(".graph-canvas")!;
    await waitFor(() =>
      expect(canvas).toHaveAttribute("data-motion-active", "true"),
    );
    const graphSection = container.querySelector(".graph-workspace")!;
    act(() =>
      notify(
        [
          {
            target: graphSection,
            isIntersecting: false,
          } as IntersectionObserverEntry,
        ],
        {} as IntersectionObserver,
      ),
    );
    expect(canvas).toHaveAttribute("data-motion-active", "false");
    fireEvent.keyDown(
      screen.getAllByRole("button", { name: "address: Synthetic office" })[0],
      { key: "Enter" },
    );
    expect(
      within(container.querySelector(".graph-inspector")!).getByText(
        "Recorded value",
      ),
    ).toBeInTheDocument();
    expect(
      within(container.querySelector(".graph-inspector")!).getByText(
        "Saved relationship",
      ),
    ).toBeInTheDocument();
    const hidden = vi.spyOn(document, "hidden", "get").mockReturnValue(true);
    act(() => {
      notify(
        [
          {
            target: graphSection,
            isIntersecting: true,
          } as IntersectionObserverEntry,
        ],
        {} as IntersectionObserver,
      );
      document.dispatchEvent(new Event("visibilitychange"));
    });
    expect(canvas).toHaveAttribute("data-motion-active", "false");
    expect("__transition" in canvas.querySelector("svg")!).toBe(false);
    hidden.mockReturnValue(false);
    act(() => document.dispatchEvent(new Event("visibilitychange")));
    expect(canvas).toHaveAttribute("data-motion-active", "true");
    unmount();
    expect(stop).toHaveBeenCalled();
    expect(canvas.childElementCount).toBe(0);
    hidden.mockRestore();
  });

  it("shows neutral selected-edge accents only for visible evidence and clears them with selection", async () => {
    const { container } = render(<GraphExplorer graph={graph} />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Fit" })).toBeEnabled(),
    );
    const accents = () =>
      Array.from(
        container.querySelectorAll<SVGPathElement>(".graph-link-glint"),
      ).filter((edge) => edge.style.display !== "none");
    expect(accents()).toHaveLength(0);
    fireEvent.keyDown(
      screen.getByRole("button", { name: "company: Synthetic Company One" }),
      { key: "Enter" },
    );
    expect(accents()).toHaveLength(1);
    expect(container.querySelectorAll("marker")).toHaveLength(0);
    fireEvent.click(screen.getByLabelText("Address"));
    expect(accents()).toHaveLength(0);
    expect(
      Array.from(
        container.querySelectorAll<SVGPathElement>(".graph-link-hit"),
      ).every((edge) => edge.style.display === "none"),
    ).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Clear selection" }));
    expect(accents()).toHaveLength(0);
    expect(
      screen.getByRole("button", { name: "company: Synthetic Company One" }),
    ).toHaveAttribute("aria-pressed", "false");
  });
});

describe("graph Save View contract", () => {
  it("removes a browser view without moving nodes and allows saving it again", async () => {
    const { container } = render(<GraphExplorer graph={graph} />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save view" })).toBeEnabled(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Save view" }));
    const before = container
      .querySelector(".graph-node")
      ?.getAttribute("transform");
    expect(localStorage.getItem(graphStorageKey(graph.cluster))).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Remove saved view" }));
    expect(localStorage.getItem(graphStorageKey(graph.cluster))).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Remove saved view" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Restore saved view" }),
    ).toBeDisabled();
    expect(
      container.querySelector(".graph-node")?.getAttribute("transform"),
    ).toEqual(before);
    fireEvent.click(screen.getByRole("button", { name: "Save view" }));
    expect(localStorage.getItem(graphStorageKey(graph.cluster))).not.toBeNull();
  });

  it("removes an account view with CSRF and uses the returned revision for re-save", async () => {
    state.user = { id: 7, username: "synthetic-user", role: "user" };
    const fetcher = vi.fn(async (_url: string, options: RequestInit) => {
      if (options.method === "DELETE") {
        expect(JSON.parse(String(options.body))).toEqual({ revision: 4 });
        expect(options.headers).toMatchObject({
          "X-CSRFToken": "synthetic-csrf",
        });
        return json({ revision: 5, payload: null });
      }
      if (options.method === "PUT") {
        const body = JSON.parse(String(options.body));
        expect(body.revision).toBe(5);
        return json({ revision: 6, payload: body.payload });
      }
      return json({ revision: 4, payload: { frozen: true, positions: {} } });
    });
    vi.stubGlobal("fetch", fetcher);
    render(<GraphExplorer graph={graph} />);
    fireEvent.click(
      await screen.findByRole("button", { name: "Remove saved view" }),
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "Remove saved view" }),
      ).not.toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Save view" }));
    await screen.findByRole("button", { name: "Remove saved view" });
    expect(fetcher.mock.calls.map(([, options]) => options.method)).toEqual([
      "GET",
      "DELETE",
      "PUT",
    ]);
  });

  it("does not reload an old guest layout after an account view was removed", async () => {
    state.user = { id: 7, username: "synthetic-user", role: "user" };
    localStorage.setItem(
      graphStorageKey(graph.cluster),
      JSON.stringify({ frozen: true, selected: "company:1", positions: {} }),
    );
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => json({ revision: 5, payload: null })),
    );
    render(<GraphExplorer graph={graph} />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save view" })).toBeEnabled(),
    );
    expect(
      screen.queryByRole("button", { name: "Remove saved view" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/Browser view loaded/)).not.toBeInTheDocument();
  });

  it("retains the saved view and blocks stale writes if removal conflicts", async () => {
    state.user = { id: 7, username: "synthetic-user", role: "user" };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string, options: RequestInit) =>
        options.method === "DELETE"
          ? json(
              {
                error: {
                  code: "view_conflict",
                  message: "View changed in another tab.",
                },
              },
              409,
            )
          : json({ revision: 2, payload: { frozen: true, positions: {} } }),
      ),
    );
    render(<GraphExplorer graph={graph} />);
    fireEvent.click(
      await screen.findByRole("button", { name: "Remove saved view" }),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Reload saved account view" }),
      ).toBeEnabled(),
    );
    expect(screen.getByRole("button", { name: "Save view" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Remove saved view" }),
    ).toBeDisabled();
  });

  it("saves the final focus camera to the account and restores its coordinates, filters and selection after a fresh mount", async () => {
    state.user = { id: 7, username: "synthetic-user", role: "user" };
    vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(900);
    vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(650);
    let saved: GraphView = {
      revision: 4,
      payload: {
        positions: {
          "company:1": { x: 100, y: 150, pinned: true },
          "company:2": { x: 450, y: 80, pinned: false },
          "contact:1": { x: 280, y: -180, pinned: false },
        },
        zoom: { x: 0, y: 0, k: 1 },
        filters: ["address"],
        selected: null,
        frozen: true,
      },
    };
    const fetcher = vi.fn(async (_url: string, options: RequestInit) => {
      if (options.method !== "PUT") return json(saved);
      const body = JSON.parse(String(options.body));
      expect(Object.keys(body).sort()).toEqual([
        "graph_hash",
        "payload",
        "revision",
        "snapshot_id",
      ]);
      expect(body).toMatchObject({
        graph_hash: graph.graph_hash,
        snapshot_id: graph.snapshot_id,
        revision: saved.revision,
      });
      saved = { revision: saved.revision + 1, payload: body.payload };
      return json(saved);
    });
    vi.stubGlobal("fetch", fetcher);
    const first = render(<GraphExplorer graph={graph} />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save view" })).toBeEnabled(),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "company: Synthetic Company One" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Focus this node" }));
    expect(
      "__transition" in first.container.querySelector(".graph-canvas > svg")!,
    ).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Save view" }));
    await waitFor(() =>
      expect(
        first.container.querySelector(".graph-save-feedback"),
      ).toHaveAttribute("data-state", "success"),
    );
    expect(saved.payload).toMatchObject({
      zoom: { x: 350, y: 175, k: 1 },
      positions: { "company:1": { x: 100, y: 150, pinned: true } },
      filters: ["address"],
      selected: "company:1",
      frozen: true,
    });
    expect(fetcher.mock.calls[1][0]).toBe(
      "/api/v1/clusters/synthetic-cluster/view/",
    );
    expect(fetcher.mock.calls[1][1]).toMatchObject({
      method: "PUT",
      credentials: "same-origin",
      headers: { "X-CSRFToken": "synthetic-csrf" },
    });
    expect(localStorage.getItem(graphStorageKey(graph.cluster))).toBeNull();
    first.unmount();
    const second = render(<GraphExplorer graph={graph} />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save view" })).toBeEnabled(),
    );
    expect(
      second.container.querySelector('[data-node-id="company:1"]'),
    ).toHaveAttribute("transform", "translate(100,150)");
    expect(
      screen.getByRole("button", { name: "company: Synthetic Company One" }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByLabelText("Director")).not.toBeChecked();
    expect(
      second.container.querySelector(".graph-canvas > svg > g"),
    ).toHaveAttribute("transform", "translate(350,175) scale(1)");
    fireEvent.click(screen.getByRole("button", { name: "Save view" }));
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(4));
    expect(JSON.parse(String(fetcher.mock.calls[3][1].body)).revision).toBe(5);
  });

  it("does not issue a revision-zero PUT after a private-view read fails and recovers without resetting the current arrangement", async () => {
    state.user = { id: 7, username: "synthetic-user", role: "user" };
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        json(
          {
            error: {
              code: "request_error",
              message: "Synthetic view temporarily unavailable.",
            },
          },
          503,
        ),
      )
      .mockResolvedValueOnce(json({ revision: 0, payload: null }))
      .mockImplementationOnce(async (_url: string, options: RequestInit) =>
        json({
          revision: 1,
          payload: JSON.parse(String(options.body)).payload,
        }),
      );
    vi.stubGlobal("fetch", fetcher);
    const { container } = render(<GraphExplorer graph={graph} />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Fit" })).toBeEnabled(),
    );
    expect(screen.getByRole("button", { name: "Save view" })).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "temporarily unavailable",
    );
    fireEvent.click(
      screen.getByRole("button", { name: "company: Synthetic Company One" }),
    );
    const node = container.querySelector('[data-node-id="company:1"]')!;
    const before = node.getAttribute("transform");
    fireEvent.click(screen.getByRole("button", { name: "Save view" }));
    expect(fetcher).toHaveBeenCalledTimes(1);
    fireEvent.click(
      screen.getByRole("button", { name: "Reload saved account view" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save view" })).toBeEnabled(),
    );
    expect(container.querySelector('[data-node-id="company:1"]')).toBe(node);
    expect(node.getAttribute("transform")).toBe(before);
    expect(node).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "Save view" }));
    await waitFor(() =>
      expect(container.querySelector(".graph-save-feedback")).toHaveAttribute(
        "data-state",
        "success",
      ),
    );
    expect(JSON.parse(String(fetcher.mock.calls[2][1].body))).toMatchObject({
      revision: 0,
      snapshot_id: graph.snapshot_id,
      payload: { selected: "company:1" },
    });
  });

  it("keeps keyboard panning and zooming when saving or pausing after a completed camera transition", async () => {
    vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(900);
    vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(650);
    localStorage.setItem(
      graphStorageKey(graph.cluster),
      JSON.stringify({
        positions: { "company:1": { x: 100, y: 150, pinned: true } },
        zoom: { x: 0, y: 0, k: 1 },
        frozen: true,
      }),
    );
    const { container } = render(
      <MotionPreferences>
        <MotionSwitch />
        <GraphExplorer graph={graph} />
      </MotionPreferences>,
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save view" })).toBeEnabled(),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "company: Synthetic Company One" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Focus this node" }));
    const canvas = container.querySelector<HTMLDivElement>(".graph-canvas")!,
      svg = canvas.querySelector("svg")!;
    await waitFor(() => expect("__transition" in svg).toBe(false));
    fireEvent.keyDown(canvas, { key: "ArrowRight" });
    fireEvent.keyDown(canvas, { key: "+" });
    const manual = container
      .querySelector(".graph-canvas > svg > g")!
      .getAttribute("transform");
    fireEvent.click(screen.getByRole("button", { name: "Pause graph motion" }));
    expect(container.querySelector(".graph-canvas > svg > g")).toHaveAttribute(
      "transform",
      manual!,
    );
    fireEvent.click(screen.getByRole("button", { name: "Save view" }));
    expect(container.querySelector(".graph-canvas > svg > g")).toHaveAttribute(
      "transform",
      manual!,
    );
    expect(
      JSON.parse(localStorage.getItem(graphStorageKey(graph.cluster))!).zoom.k,
    ).toBe(1.25);
  });

  it("collects API-valid minimum zoom after fitting an extremely wide saved layout", async () => {
    vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(900);
    vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(650);
    localStorage.setItem(
      graphStorageKey(graph.cluster),
      JSON.stringify({
        positions: {
          "company:1": { x: -999999, y: 0, pinned: true },
          "company:2": { x: 999999, y: 0, pinned: true },
          "contact:1": { x: 0, y: 0, pinned: true },
        },
        frozen: true,
      }),
    );
    render(<GraphExplorer graph={graph} />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save view" })).toBeEnabled(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Fit" }));
    fireEvent.click(screen.getByRole("button", { name: "Save view" }));
    const payload = JSON.parse(
      localStorage.getItem(graphStorageKey(graph.cluster))!,
    ) as ViewPayload;
    expect(payload.zoom?.k).toBe(0.05);
    expect(payload.positions?.["company:1"].x).toBe(-999999);
    expect(payload.positions?.["company:2"].x).toBe(999999);
  });
});

describe("guest layout handoff to an account", () => {
  const browserLayout: ViewPayload = {
    positions: { "company:1": { x: 420, y: -180, pinned: true } },
    zoom: { x: 80, y: 240, k: 0.75 },
    filters: ["address"],
    selected: "company:1",
    frozen: true,
  };
  it("keeps a guest view after sign-in when the account has no view and requires explicit Save view to copy it", async () => {
    localStorage.setItem(
      graphStorageKey(graph.cluster),
      JSON.stringify(browserLayout),
    );
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(json({ revision: 0, payload: null }))
      .mockImplementationOnce(async (_url: string, options: RequestInit) =>
        json({
          revision: 1,
          payload: JSON.parse(String(options.body)).payload,
        }),
      );
    vi.stubGlobal("fetch", fetcher);
    const { container, rerender } = render(<GraphExplorer graph={graph} />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save view" })).toBeEnabled(),
    );
    expect(
      container.querySelector('[data-node-id="company:1"]'),
    ).toHaveAttribute("transform", "translate(420,-180)");
    expect(fetcher).not.toHaveBeenCalled();
    state.user = { id: 7, username: "synthetic-user", role: "user" };
    rerender(<GraphExplorer graph={graph} />);
    await waitFor(() =>
      expect(container.querySelector(".graph-save-feedback")).toHaveTextContent(
        "Save view to copy it to your account",
      ),
    );
    expect(
      container.querySelector('[data-node-id="company:1"]'),
    ).toHaveAttribute("transform", "translate(420,-180)");
    expect(
      screen.getByRole("button", { name: "company: Synthetic Company One" }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByLabelText("Director")).not.toBeChecked();
    expect(fetcher).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Save view" }));
    await waitFor(() =>
      expect(container.querySelector(".graph-save-feedback")).toHaveAttribute(
        "data-state",
        "success",
      ),
    );
    expect(JSON.parse(String(fetcher.mock.calls[1][1].body))).toMatchObject({
      revision: 0,
      payload: browserLayout,
    });
    expect(
      JSON.parse(localStorage.getItem(graphStorageKey(graph.cluster))!),
    ).toEqual(browserLayout);
  });

  it.each(["existing", "failed"] as const)(
    "does not import a browser view over an %s account response",
    async (scenario) => {
      localStorage.setItem(
        graphStorageKey(graph.cluster),
        JSON.stringify(browserLayout),
      );
      state.user = { id: 7, username: "synthetic-user", role: "user" };
      const fetcher = vi.fn().mockResolvedValue(
        scenario === "existing"
          ? json({
              revision: 3,
              payload: {
                positions: { "company:1": { x: -250, y: 600, pinned: true } },
                frozen: true,
              },
            })
          : json(
              {
                error: {
                  code: "request_error",
                  message: "Synthetic read failed.",
                },
              },
              503,
            ),
      );
      vi.stubGlobal("fetch", fetcher);
      const { container } = render(<GraphExplorer graph={graph} />);
      await waitFor(() =>
        expect(screen.getByRole("button", { name: "Fit" })).toBeEnabled(),
      );
      expect(
        container.querySelector('[data-node-id="company:1"]'),
      ).not.toHaveAttribute("transform", "translate(420,-180)");
      if (scenario === "existing")
        expect(
          container.querySelector('[data-node-id="company:1"]'),
        ).toHaveAttribute("transform", "translate(-250,600)");
      else
        expect(
          screen.getByRole("button", { name: "Save view" }),
        ).toBeDisabled();
      expect(
        container.querySelector(".graph-save-feedback")?.textContent ?? "",
      ).not.toContain("Browser view loaded");
      expect(fetcher).toHaveBeenCalledTimes(1);
    },
  );
});

describe("personal graph save conflicts", () => {
  it("requires a graph reload for a snapshot conflict and does not pretend a view-only retry can resolve it", async () => {
    state.user = { id: 7, username: "synthetic-user", role: "user" };
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(json({ revision: 0, payload: null }))
      .mockResolvedValueOnce(
        json(
          {
            error: {
              code: "view_conflict",
              message: "The current graph changed. Reload before saving.",
            },
          },
          409,
        ),
      );
    vi.stubGlobal("fetch", fetcher);
    const { container } = render(<GraphExplorer graph={graph} />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save view" })).toBeEnabled(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Save view" }));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "open the latest graph",
      ),
    );
    expect(screen.getByRole("button", { name: "Save view" })).toBeDisabled();
    expect(
      screen.queryByRole("button", { name: "Reload saved account view" }),
    ).not.toBeInTheDocument();
    expect(container.querySelectorAll(".graph-node")).toHaveLength(3);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});

describe("graph language switching", () => {
  it("updates D3 labels while preserving unsaved positions, pins, camera, filters, selection and browser storage", async () => {
    const saved = {
      positions: {
        "company:1": { x: 420, y: -180, pinned: false },
        "company:2": { x: -100, y: 250, pinned: true },
        "contact:1": { x: 40, y: 50, pinned: false },
      },
      zoom: { x: 90, y: 70, k: 0.9 },
      frozen: true,
      filters: ["address", "director"],
    };
    const original = JSON.stringify(saved);
    localStorage.setItem(graphStorageKey(graph.cluster), original);
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    const { container } = render(<GraphExplorer graph={graph} />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save view" })).toBeEnabled(),
    );
    const canvas = container.querySelector(".graph-canvas")!;
    const svg = canvas.querySelector("svg")!;
    const node = container.querySelector('[data-node-id="company:1"]')!;
    fireEvent.keyDown(node, { key: "p" });
    fireEvent.keyDown(canvas, { key: "ArrowRight" });
    fireEvent.keyDown(canvas, { key: "+" });
    fireEvent.click(screen.getByLabelText("Director"));
    fireEvent.change(
      screen.getByPlaceholderText("Company, BIN, person or contact"),
      { target: { value: "000000000002" } },
    );
    const camera = svg.querySelector("g")!.getAttribute("transform");
    const positions = [...container.querySelectorAll(".graph-node")].map(
      (item) => item.getAttribute("transform"),
    );
    act(() => setLanguage("ru"));
    expect(canvas.querySelector("svg")).toBe(svg);
    expect(container.querySelector('[data-node-id="company:1"]')).toBe(node);
    expect(svg.querySelector("g")).toHaveAttribute("transform", camera);
    expect(
      [...container.querySelectorAll(".graph-node")].map((item) =>
        item.getAttribute("transform"),
      ),
    ).toEqual(positions);
    expect(node).toHaveClass("pinned");
    expect(node).toHaveAttribute("aria-pressed", "true");
    expect(node).toHaveAttribute(
      "aria-label",
      "компания: Synthetic Company One",
    );
    expect(
      screen.getByRole("button", { name: "Открепить узел" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Адрес")).toBeChecked();
    expect(screen.getByLabelText("Руководитель")).not.toBeChecked();
    expect(
      screen.getByRole("button", { name: "Продолжить раскладку" }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(
      screen.getByPlaceholderText("Компания, БИН, человек или контакт"),
    ).toHaveValue("000000000002");
    expect(localStorage.getItem(graphStorageKey(graph.cluster))).toBe(original);
    expect(fetcher).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Сохранить вид" }));
    const updated = JSON.parse(
      localStorage.getItem(graphStorageKey(graph.cluster))!,
    );
    expect(updated).toMatchObject({
      positions: { "company:1": { x: 420, y: -180, pinned: true } },
      selected: "company:1",
      frozen: true,
      filters: ["address"],
    });
    expect(updated.zoom).not.toEqual(saved.zoom);
    act(() => setLanguage("en"));
    expect(canvas.querySelector("svg")).toBe(svg);
    expect(node).toHaveAttribute(
      "aria-label",
      "company: Synthetic Company One",
    );
    expect(screen.getByRole("button", { name: "Save view" })).toBeEnabled();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Selected Synthetic Company One",
    );
  });

  it("keeps private revision fencing through locale changes and does not refetch or save automatically", async () => {
    state.user = { id: 7, username: "synthetic-user", role: "user" };
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(json({ revision: 4, payload: { frozen: true } }))
      .mockResolvedValueOnce(
        json(
          {
            error: { code: "view_conflict", message: "Reload before saving." },
          },
          409,
        ),
      );
    vi.stubGlobal("fetch", fetcher);
    const { container } = render(<GraphExplorer graph={graph} />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save view" })).toBeEnabled(),
    );
    const svg = container.querySelector(".graph-canvas svg");
    act(() => setLanguage("ru"));
    expect(fetcher).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Сохранить вид" }));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("другой вкладке"),
    );
    expect(JSON.parse(String(fetcher.mock.calls[1][1].body)).revision).toBe(4);
    expect(
      screen.getByRole("button", { name: "Сохранить вид" }),
    ).toBeDisabled();
    act(() => setLanguage("en"));
    expect(screen.getByRole("button", { name: "Save view" })).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("another tab");
    expect(container.querySelector(".graph-canvas svg")).toBe(svg);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
