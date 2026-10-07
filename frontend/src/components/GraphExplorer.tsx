import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import {
  EnterFullScreenIcon,
  ResetIcon,
  BookmarkIcon,
  ReloadIcon,
  LockClosedIcon,
  LockOpen1Icon,
  MagnifyingGlassIcon,
  Cross2Icon,
} from "@radix-ui/react-icons";
import { apiFetch, ApiError, getJson, queryPath } from "../lib/api";
import type {
  GraphEdge,
  GraphNode,
  GraphResponse,
  GraphView,
  ViewPayload,
} from "../lib/types";
import { useSession } from "./Session";
import { TechHeading } from "./motion/TechHeading";
import { useDecorationActive } from "./motion/useDecorationActive";
import "./graph.css";
import "./graph-visuals.css";

export const RELATIONSHIPS = [
  "director",
  "owner",
  "address",
  "phone",
  "email",
] as const;
type Relationship = (typeof RELATIONSHIPS)[number];
type Node = GraphNode & d3.SimulationNodeDatum & { pinned?: boolean };
type Edge = Omit<GraphEdge, "source" | "target"> & d3.SimulationLinkDatum<Node>;
type Path = { nodes: string[]; edges: string[] };
type Adjacent = { node: string; edge: Edge };
const idOf = (node: string | number | Node) =>
  typeof node === "object" ? node.id : String(node);
const nodeX = (node: Node) => node.x ?? 0;
const nodeY = (node: Node) => node.y ?? 0;

// Keep the original key so anonymous views survive the React migration.
export const graphStorageKey = (cluster: string) =>
  `grafzakup.graph-view.v1.${cluster}`;

export function sanitizeView(value: unknown): ViewPayload | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const source = value as Record<string, unknown>,
    result: ViewPayload = {};
  if (
    source.positions &&
    typeof source.positions === "object" &&
    !Array.isArray(source.positions)
  ) {
    result.positions = {};
    for (const [id, raw] of Object.entries(source.positions)) {
      if (!raw || typeof raw !== "object" || Array.isArray(raw)) continue;
      const item = raw as Record<string, unknown>;
      if (
        typeof item.x === "number" &&
        typeof item.y === "number" &&
        Number.isFinite(item.x) &&
        Number.isFinite(item.y) &&
        Math.abs(item.x) <= 1e6 &&
        Math.abs(item.y) <= 1e6
      )
        result.positions[id] = {
          x: item.x,
          y: item.y,
          pinned: item.pinned === true,
        };
    }
  }
  if (source.zoom && typeof source.zoom === "object") {
    const zoom = source.zoom as Record<string, unknown>;
    if (
      typeof zoom.x === "number" &&
      typeof zoom.y === "number" &&
      typeof zoom.k === "number" &&
      [zoom.x, zoom.y, zoom.k].every(Number.isFinite) &&
      Math.abs(zoom.x) <= 1e7 &&
      Math.abs(zoom.y) <= 1e7 &&
      zoom.k >= 0.05 &&
      zoom.k <= 8
    )
      result.zoom = { x: zoom.x, y: zoom.y, k: zoom.k };
  }
  if (Array.isArray(source.filters))
    result.filters = [
      ...new Set(
        source.filters.filter(
          (item): item is Relationship =>
            typeof item === "string" &&
            RELATIONSHIPS.includes(item as Relationship),
        ),
      ),
    ];
  if (typeof source.selected === "string" || source.selected === null)
    result.selected = source.selected;
  if (typeof source.frozen === "boolean") result.frozen = source.frozen;
  return result;
}

export function wrappedLabel(
  value: string,
  width = 24,
  maxLines = 3,
): string[] {
  const words = String(value)
    .split(/\s+/)
    .flatMap((word) => {
      const chars = Array.from(word),
        chunks = [];
      for (let index = 0; index < chars.length; index += width)
        chunks.push(chars.slice(index, index + width).join(""));
      return chunks;
    });
  const lines = [""];
  for (const word of words) {
    if (lines.at(-1) && lines.at(-1)!.length + word.length + 1 > width)
      lines.push("");
    lines[lines.length - 1] += (lines.at(-1) ? " " : "") + word;
  }
  return lines.length > maxLines
    ? [
        ...lines.slice(0, maxLines - 1),
        lines[maxLines - 1].slice(0, width - 1) + "…",
      ]
    : lines;
}

export function adjacency(
  nodes: Node[],
  links: Edge[],
  filters: readonly string[] = RELATIONSHIPS,
): Map<string, Adjacent[]> {
  const map = new Map<string, Adjacent[]>(nodes.map((node) => [node.id, []]));
  for (const edge of links) {
    if (!filters.includes(edge.type)) continue;
    const from = idOf(edge.source),
      to = idOf(edge.target);
    if (map.has(from) && map.has(to)) {
      map.get(from)!.push({ node: to, edge });
      map.get(to)!.push({ node: from, edge });
    }
  }
  return map;
}

export function shortestPath(
  nodes: Node[],
  links: Edge[],
  from: string,
  to: string,
  filters: readonly string[] = RELATIONSHIPS,
): Path | null {
  const map = adjacency(nodes, links, filters);
  if (!map.has(from) || !map.has(to)) return null;
  const previous = new Map<string, { from: string; edge: string } | null>([
      [from, null],
    ]),
    queue = [from];
  for (let index = 0; index < queue.length && !previous.has(to); index++) {
    for (const item of map.get(queue[index])!) {
      if (!previous.has(item.node)) {
        previous.set(item.node, { from: queue[index], edge: item.edge.id });
        queue.push(item.node);
      }
    }
  }
  if (!previous.has(to)) return null;
  const path: Path = { nodes: [to], edges: [] };
  while (path.nodes[0] !== from) {
    const step = previous.get(path.nodes[0])!;
    path.edges.unshift(step.edge);
    path.nodes.unshift(step.from);
  }
  return path;
}

export function restorePositions(
  nodes: Node[],
  links: Edge[],
  payload: ViewPayload | null,
): void {
  const positions = payload?.positions ?? {},
    byId = new Map(nodes.map((node) => [node.id, node]));
  const saved = new Set<string>(),
    neighbours = adjacency(nodes, links);
  for (const node of nodes) {
    const position = positions[node.id];
    if (
      position &&
      Number.isFinite(position.x) &&
      Number.isFinite(position.y) &&
      Math.abs(position.x) <= 1e6 &&
      Math.abs(position.y) <= 1e6
    ) {
      Object.assign(node, {
        x: position.x,
        y: position.y,
        pinned: position.pinned === true,
      });
      saved.add(node.id);
    }
  }
  const grid = new Map<string, Node[]>(),
    spacing = 250;
  const cell = (x: number, y: number) =>
    `${Math.floor(x / spacing)}:${Math.floor(y / spacing)}`;
  const record = (node: Node) => {
    const key = cell(nodeX(node), nodeY(node));
    grid.set(key, [...(grid.get(key) ?? []), node]);
  };
  const crowded = (x: number, y: number) => {
    const cx = Math.floor(x / spacing),
      cy = Math.floor(y / spacing);
    for (let dx = -1; dx <= 1; dx++)
      for (let dy = -1; dy <= 1; dy++) {
        if (
          (grid.get(`${cx + dx}:${cy + dy}`) ?? []).some(
            (node) => Math.hypot(x - nodeX(node), y - nodeY(node)) < spacing,
          )
        )
          return true;
      }
    return false;
  };
  nodes.filter((node) => saved.has(node.id)).forEach(record);
  nodes.forEach((node, index) => {
    if (saved.has(node.id)) return;
    const anchors = (neighbours.get(node.id) ?? [])
      .filter((item) => saved.has(item.node))
      .map((item) => byId.get(item.node)!);
    const centreX = anchors.length
      ? anchors.reduce((sum, item) => sum + nodeX(item), 0) / anchors.length
      : 0;
    const centreY = anchors.length
      ? anchors.reduce((sum, item) => sum + nodeY(item), 0) / anchors.length
      : 0;
    for (let attempt = 0; attempt < 48; attempt++) {
      const angle = index * 2.399963 + attempt * 0.618;
      const radius =
        (anchors.length ? 300 : Math.max(180, Math.sqrt(index + 1) * 120)) +
        Math.floor(attempt / 8) * 160;
      node.x = centreX + Math.cos(angle) * radius;
      node.y = centreY + Math.sin(angle) * radius;
      if (!crowded(nodeX(node), nodeY(node))) break;
    }
    node.pinned = false;
    record(node);
  });
}

export function safeGraphLink(value: unknown): string | null {
  if (typeof value !== "string" || /[\s\u0000-\u001f\u007f\\]/.test(value))
    return null;
  if (value.startsWith("/") && !value.startsWith("//")) return value;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password
      ? value
      : null;
  } catch {
    return null;
  }
}

function contactIcon(type: string | undefined): string {
  if (type === "phone")
    return "M-5,-7l3,-1l3,5l-2,2q2,4 6,6l2,-2l5,3l-1,3q-12,1 -16,-12z";
  if (type === "email") return "M-7,-5h14v10h-14z M-7,-5l7,5l7,-5";
  return "M-6,-2a6,6 0 1,1 12,0q0,5 -6,11q-6,-6 -6,-11z M-2,-2a2,2 0 1,0 4,0a2,2 0 1,0 -4,0";
}

type Controller = {
  fit: () => void;
  reset: () => void;
  restore: () => void;
  freeze: () => void;
  filter: (values: Relationship[]) => void;
  search: (value: string) => Node[];
  select: (id: string) => void;
  clear: () => void;
  collect: () => ViewPayload;
  setSaved: (value: ViewPayload | null) => void;
  setMotion: (allowed: boolean) => void;
  destroy: () => void;
};

function mountGraph(
  container: HTMLDivElement,
  inspector: HTMLDivElement,
  response: GraphResponse,
  initial: ViewPayload | null,
  report: (message: string) => void,
  onFilters: (values: Relationship[]) => void,
  onFrozen: (frozen: boolean) => void,
  initialMotion: boolean,
): Controller {
  const nodes: Node[] = response.graph.nodes.map((node) => ({ ...node }));
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const links: Edge[] = response.graph.links
    .filter((edge) => byId.has(edge.source) && byId.has(edge.target))
    .map((edge) => ({ ...edge }));
  const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  let decorationAllowed = initialMotion;
  let motionMS = decorationAllowed && !motionQuery.matches ? 320 : 0;
  let cameraTarget: d3.ZoomTransform | null = null;
  let revealed = false;
  let saved = initial,
    selected: string | null = null,
    selectedEdge: string | null = null,
    pathStart: string | null = null,
    path: Path | null = null;
  let frozen = saved ? saved.frozen !== false : false;
  let filters: Relationship[] = saved?.filters
    ? (saved.filters.filter((value) =>
        RELATIONSHIPS.includes(value as Relationship),
      ) as Relationship[])
    : [...RELATIONSHIPS];
  restorePositions(nodes, links, saved);
  const svg = d3
    .select(container)
    .append("svg")
    .attr("aria-label", "Companies, verified people and shared contacts");
  const defs = svg.append("defs");
  const suffix = response.snapshot_id ?? "empty";
  for (const [kind, from, to] of [
    ["company", "#173b68", "#071426"],
    ["person", "#352a58", "#111023"],
    ["contact", "#243243", "#09131f"],
  ]) {
    const gradient = defs
      .append("linearGradient")
      .attr("id", `graph-${kind}-fill-${suffix}`)
      .attr("x1", "0%")
      .attr("y1", "0%")
      .attr("x2", "100%")
      .attr("y2", "100%");
    gradient.append("stop").attr("offset", "0%").attr("stop-color", from);
    gradient.append("stop").attr("offset", "100%").attr("stop-color", to);
  }
  const layer = svg.append("g");
  const tooltip = d3
    .select(container)
    .append("div")
    .attr("class", "graph-tooltip")
    .style("display", "none");
  const zoom = d3
    .zoom<SVGSVGElement, unknown>()
    .extent(() => [
      [0, 0],
      [Math.max(1, container.clientWidth), Math.max(1, container.clientHeight)],
    ])
    .scaleExtent([0.05, 8])
    .on("zoom", (event) => {
      if (event.sourceEvent) cameraTarget = null;
      layer.attr("transform", event.transform);
    });
  svg.call(zoom).on("dblclick.zoom", null);
  const line = layer
    .append("g")
    .selectAll<SVGPathElement, Edge>("path")
    .data(links)
    .join("path")
    .attr(
      "class",
      (edge) =>
        `graph-link edge-${edge.type}${["address", "phone", "email"].includes(edge.type) ? " weak" : ""}`,
    )
    .attr("tabindex", 0)
    .attr("role", "button")
    .attr("aria-label", (edge) => `${edge.type}: ${edge.value}`)
    .on("click", (_, edge) => inspectEdge(edge))
    .on("keydown", (event: KeyboardEvent, edge) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        inspectEdge(edge);
      }
    })
    .on("mouseover", (event: MouseEvent, edge) =>
      showTooltip(
        event,
        `${edge.type}: ${edge.value} · confidence ${edge.confidence}`,
      ),
    )
    .on("mouseout", () => tooltip.style("display", "none"));
  // Wider transparent targets make thin evidence lines easier to inspect.
  const hitLine = layer
    .append("g")
    .attr("aria-hidden", "true")
    .selectAll<SVGPathElement, Edge>("path")
    .data(links)
    .join("path")
    .attr("class", "graph-link-hit")
    .on("click", (_, edge) => inspectEdge(edge))
    .on("mouseover", (event: MouseEvent, edge) =>
      showTooltip(
        event,
        `${edge.type}: ${edge.value} · confidence ${edge.confidence}`,
      ),
    )
    .on("mouseout", () => tooltip.style("display", "none"));
  const glowLine = layer
    .append("g")
    .attr("aria-hidden", "true")
    .selectAll<SVGPathElement, Edge>("path")
    .data(links)
    .join("path")
    .attr("class", (edge) => `graph-link-glint edge-${edge.type}`)
    .attr("pathLength", 100);
  const edgeLabel = layer
    .append("g")
    .selectAll<SVGGElement, Edge>("g")
    .data(links)
    .join("g")
    .attr("class", (edge) => `graph-edge-label edge-${edge.type}`)
    .on("click", (_, edge) => inspectEdge(edge));
  edgeLabel
    .append("rect")
    .attr("x", -32)
    .attr("y", -11)
    .attr("width", 64)
    .attr("height", 22)
    .attr("rx", 10);
  edgeLabel
    .append("text")
    .attr("text-anchor", "middle")
    .attr("y", 4)
    .text((edge) => edge.type);
  const groups = layer
    .append("g")
    .selectAll<SVGGElement, Node>("g")
    .data(nodes)
    .join("g")
    .attr(
      "class",
      (node) =>
        `graph-node node-${node.kind}${node.contact_type ? ` edge-${node.contact_type}` : ""}`,
    )
    .attr("tabindex", 0)
    .attr("role", "button")
    .attr("data-node-id", (node) => node.id)
    .attr("aria-pressed", "false")
    .attr("aria-label", (node) => `${node.kind}: ${node.name}`)
    .on("click", (event: MouseEvent, node) => {
      if (!event.defaultPrevented) {
        selectNode(node.id);
        if (d3.zoomTransform(svg.node()!).k < 0.6) focusNode(node);
      }
    })
    .on("keydown", (event: KeyboardEvent, node) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectNode(node.id);
      }
      if (event.key.toLowerCase() === "p") {
        node.pinned = !node.pinned;
        applyFrozen();
        selectNode(node.id);
      }
    })
    .on("dblclick", (event: MouseEvent, node) => {
      event.preventDefault();
      node.pinned = !node.pinned;
      applyFrozen();
      updateHighlights();
      report(node.pinned ? "Node pinned." : "Node unpinned.");
    })
    .on("mouseover", (event: MouseEvent, node) =>
      showTooltip(event, `${node.kind}: ${node.name}`),
    )
    .on("mouseout", () => tooltip.style("display", "none"));
  groups.each(function (node) {
    const group = d3.select(this);
    if (node.kind === "company") {
      group
        .append("rect")
        .attr("x", -112)
        .attr("y", -65)
        .attr("width", 224)
        .attr("height", 130)
        .attr("rx", 20)
        .attr("class", "node-shape");
      group
        .append("rect")
        .attr("x", -119)
        .attr("y", -72)
        .attr("width", 238)
        .attr("height", 144)
        .attr("rx", 26)
        .attr("class", "node-aura");
      group
        .append("path")
        .attr("d", "M-95,-62h56 M105,9v31")
        .attr("class", "node-light-trim");
      group
        .append("path")
        .attr(
          "d",
          "M-96,-50l8,-4l8,4v12l-8,4l-8,-4z M-96,-50l8,4l8,-4 M-88,-46v12",
        )
        .attr("class", "node-icon");
      group
        .append("line")
        .attr("x1", -98)
        .attr("x2", 98)
        .attr("y1", -26)
        .attr("y2", -26)
        .attr("class", "node-divider");
      group
        .append("text")
        .attr("x", -75)
        .attr("y", -38)
        .attr("class", "node-category")
        .text("COMPANY");
    } else if (node.kind === "person") {
      group.append("circle").attr("r", 90).attr("class", "node-shape");
      group.append("circle").attr("r", 99).attr("class", "node-aura");
      group
        .append("path")
        .attr("d", "M-39,-81A90,90 0 0,1 39,-81 M58,69A90,90 0 0,1 22,87")
        .attr("class", "node-light-trim");
      group
        .append("path")
        .attr(
          "d",
          "M-6,-58a6,6 0 1,0 12,0a6,6 0 1,0 -12,0 M-13,-39q0,-12 13,-12q13,0 13,12",
        )
        .attr("class", "node-icon");
    } else {
      group
        .append("path")
        .attr(
          "d",
          "M-83,-60 Q-95,-60 -101,-48 L-118,-8 Q-122,0 -118,8 L-101,48 Q-95,60 -83,60 L83,60 Q95,60 101,48 L118,8 Q122,0 118,-8 L101,-48 Q95,-60 83,-60 Z",
        )
        .attr("class", "node-shape");
      group
        .append("path")
        .attr(
          "d",
          "M-83,-60 Q-95,-60 -101,-48 L-118,-8 Q-122,0 -118,8 L-101,48 Q-95,60 -83,60 L83,60 Q95,60 101,48 L118,8 Q122,0 118,-8 L101,-48 Q95,-60 83,-60 Z",
        )
        .attr("transform", "scale(1.04)")
        .attr("class", "node-aura");
      group
        .append("path")
        .attr("d", contactIcon(node.contact_type))
        .attr("transform", "translate(-88,-42)")
        .attr("class", "node-icon");
      group
        .append("text")
        .attr("text-anchor", "middle")
        .attr("y", -36)
        .attr("class", "node-category")
        .text((node.contact_type ?? "contact").toUpperCase());
    }
    group
      .select(".node-shape")
      .attr("fill", `url(#graph-${node.kind}-fill-${suffix})`);
    group
      .append("path")
      .attr("d", "M-3,-6h6v5l3,3h-12l3,-3z M0,2v5")
      .attr(
        "transform",
        node.kind === "company"
          ? "translate(96,-42)"
          : node.kind === "person"
            ? "translate(61,-59)"
            : "translate(92,-36)",
      )
      .attr("class", "node-pin");
    group.append("title").text(node.name);
    const labels = wrappedLabel(node.name, node.kind === "person" ? 22 : 28);
    const label = group.append("text").attr("text-anchor", "middle");
    labels.forEach((value, index) =>
      label
        .append("tspan")
        .attr("x", 0)
        .attr(
          "y",
          (index - (labels.length - 1) / 2) * 17 +
            (node.kind === "person" ? 9 : 1),
        )
        .text(value),
    );
    group
      .append("text")
      .attr("text-anchor", "middle")
      .attr("y", node.kind === "person" ? 60 : 48)
      .attr("class", "node-meta")
      .text(
        node.kind === "company"
          ? `BIN ${node.bin ?? "unknown"}`
          : node.kind === "person"
            ? "IDENTITY VERIFIED"
            : "SHARED CONTACT · WEAK EVIDENCE",
      );
  });
  const simulation = d3
    .forceSimulation(nodes)
    .force(
      "link",
      d3
        .forceLink<Node, Edge>(links)
        .id((node) => node.id)
        .distance(340),
    )
    .force("charge", d3.forceManyBody().strength(-1300))
    .force("collide", d3.forceCollide(145))
    .force("center", d3.forceCenter(0, 0))
    .on("tick", render);
  simulation.stop();
  groups.call(
    d3
      .drag<SVGGElement, Node>()
      .on("start", (event, node) => {
        if (!event.active && !frozen && motionMS)
          simulation.alphaTarget(0.1).restart();
        node.fx = node.x;
        node.fy = node.y;
      })
      .on("drag", (event, node) => {
        node.fx = node.x = event.x;
        node.fy = node.y = event.y;
        render();
      })
      .on("end", (event, node) => {
        if (!event.active) simulation.alphaTarget(0);
        if (!frozen && !node.pinned) {
          node.fx = null;
          node.fy = null;
        }
      }),
  );

  function showTooltip(event: MouseEvent, text: string) {
    const bounds = container.getBoundingClientRect();
    tooltip
      .text(text)
      .style(
        "left",
        Math.max(
          8,
          Math.min(event.clientX - bounds.left + 12, bounds.width - 220),
        ) + "px",
      )
      .style("top", Math.max(8, event.clientY - bounds.top + 12) + "px")
      .style("display", "block");
  }
  function render() {
    const pathFor = (edge: Edge) => {
      const a = edge.source as Node,
        b = edge.target as Node,
        offset = edge.type === "owner" ? 35 : 0;
      return `M${nodeX(a)},${nodeY(a)} Q${(nodeX(a) + nodeX(b)) / 2 + offset},${(nodeY(a) + nodeY(b)) / 2 - offset} ${nodeX(b)},${nodeY(b)}`;
    };
    line.attr("d", pathFor);
    hitLine.attr("d", pathFor);
    glowLine.attr("d", pathFor);
    edgeLabel.attr(
      "transform",
      (edge) =>
        `translate(${(nodeX(edge.source as Node) + nodeX(edge.target as Node)) / 2 + (edge.type === "owner" ? 18 : 0)},${(nodeY(edge.source as Node) + nodeY(edge.target as Node)) / 2 - (edge.type === "owner" ? 18 : 0)})`,
    );
    groups.attr(
      "transform",
      (node) => `translate(${nodeX(node)},${nodeY(node)})`,
    );
  }
  function applyFrozen(restart = true) {
    nodes.forEach((node) => {
      node.fx = frozen || node.pinned ? node.x : null;
      node.fy = frozen || node.pinned ? node.y : null;
    });
    onFrozen(frozen);
    if (frozen || !restart || !motionMS) simulation.stop();
    else simulation.alpha(0.3).restart();
    render();
  }
  function updateHighlights() {
    const neighbours = adjacency(nodes, links, filters),
      close = new Set(
        selected ? neighbours.get(selected)?.map((item) => item.node) : [],
      );
    const active = new Set(
      links
        .filter((edge) => filters.includes(edge.type as Relationship))
        .flatMap((edge) => [idOf(edge.source), idOf(edge.target)]),
    );
    const visible = (node: Node) =>
      node.kind === "company" || active.has(node.id) || node.id === selected;
    groups
      .style("display", (node) => (visible(node) ? null : "none"))
      .attr("tabindex", (node) => (visible(node) ? 0 : -1))
      .classed(
        "selected",
        (node) => node.id === selected || !!path?.nodes.includes(node.id),
      )
      .attr("aria-pressed", (node) => String(node.id === selected))
      .classed("neighbour", (node) => close.has(node.id))
      .classed("pinned", (node) => !!node.pinned)
      .classed(
        "graph-dimmed",
        (node) =>
          !!selected &&
          node.id !== selected &&
          !close.has(node.id) &&
          !path?.nodes.includes(node.id),
      );
    const highlighted = (edge: Edge) =>
      edge.id === selectedEdge || !!path?.edges.includes(edge.id);
    const dimmed = (edge: Edge) =>
      !!selected &&
      idOf(edge.source) !== selected &&
      idOf(edge.target) !== selected &&
      !highlighted(edge);
    line
      .style("display", (edge) =>
        filters.includes(edge.type as Relationship) ? null : "none",
      )
      .attr("tabindex", (edge) =>
        filters.includes(edge.type as Relationship) ? 0 : -1,
      )
      .classed("selected", highlighted)
      .classed("graph-dimmed", dimmed);
    hitLine.style("display", (edge) =>
      filters.includes(edge.type as Relationship) ? null : "none",
    );
    // A small number of accents shows selection, not direction or new evidence.
    const accents = new Set(
      links
        .filter(
          (edge) =>
            filters.includes(edge.type as Relationship) &&
            (highlighted(edge) ||
              (selected !== null &&
                (idOf(edge.source) === selected ||
                  idOf(edge.target) === selected))),
        )
        .slice(0, 12)
        .map((edge) => edge.id),
    );
    glowLine.style("display", (edge) => (accents.has(edge.id) ? null : "none"));
    edgeLabel
      .classed(
        "selected",
        (edge) =>
          highlighted(edge) ||
          (selected !== null &&
            (idOf(edge.source) === selected || idOf(edge.target) === selected)),
      )
      .style("display", (edge) =>
        filters.includes(edge.type as Relationship) ? null : "none",
      )
      .classed("graph-dimmed", dimmed);
  }
  function add(tag: string, text: string) {
    const element = document.createElement(tag);
    element.textContent = text;
    return inspector.appendChild(element);
  }
  function fact(label: string, value: string) {
    const row = add("div", "");
    row.className = "graph-inspector-fact";
    const title = document.createElement("span"),
      detail = document.createElement("strong");
    title.textContent = label;
    detail.textContent = value;
    row.append(title, detail);
  }
  function category(value: string) {
    const label = add("span", value);
    label.className = "graph-inspector-category";
  }
  function button(text: string, action: () => void) {
    const element = add("button", text) as HTMLButtonElement;
    element.type = "button";
    element.className = "button button-quiet graph-inspector-action";
    const arrow = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    arrow.setAttribute("viewBox", "0 0 16 16");
    arrow.setAttribute("aria-hidden", "true");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", "M3 8h10M8 3l5 5l-5 5");
    arrow.append(path);
    element.append(arrow);
    element.addEventListener("click", action);
  }
  function reference(text: string, value: string) {
    const url = safeGraphLink(value);
    if (!url) {
      add("p", text);
      return;
    }
    const element = add("a", text) as HTMLAnchorElement;
    element.href = url;
    element.rel = "noopener noreferrer";
    if (url.startsWith("https:")) element.target = "_blank";
  }
  function inspectEdge(edge: Edge) {
    selected = idOf(edge.source);
    selectedEdge = edge.id;
    path = null;
    inspector.replaceChildren();
    category("Saved relationship");
    add("h3", edge.type[0].toUpperCase() + edge.type.slice(1));
    add(
      "p",
      `${byId.get(idOf(edge.source))!.name} → ${byId.get(idOf(edge.target))!.name}`,
    );
    add(
      "p",
      `Relationship in saved graph v${response.version}. ${["owner", "director"].includes(edge.type) ? "Verified identity and source-backed role." : "Shared contact; affiliation and wrongdoing are not established."}`,
    );
    fact("Recorded value", edge.value);
    fact("Evidence confidence", edge.confidence);
    fact(
      "Legal interval",
      `${edge.valid_from ?? "unknown"} to ${edge.valid_until ?? "unknown"} (exclusive end)`,
    );
    for (const text of edge.limitations) add("p", text);
    for (const item of edge.evidence) {
      add(
        "p",
        `${item.quality ?? "unknown quality"} · observed ${item.observed_at ?? "unknown"}`,
      );
      reference(
        item.source +
          (item.observation_id ? ` · observation ${item.observation_id}` : ""),
        item.url ?? "",
      );
    }
    updateHighlights();
    report(`Selected ${edge.type} relationship.`);
  }
  function selectNode(id: string) {
    const node = byId.get(id);
    if (!node) return;
    selected = id;
    selectedEdge = null;
    path =
      pathStart && pathStart !== id
        ? shortestPath(nodes, links, pathStart, id, filters)
        : null;
    inspector.replaceChildren();
    category(
      node.kind === "company"
        ? "Company record"
        : node.kind === "person"
          ? "Verified person"
          : "Shared contact",
    );
    add("h3", node.name);
    if (node.bin) fact("BIN", node.bin);
    if (node.kind === "company" && node.company_id)
      reference(
        "Open company",
        `${import.meta.env.DEV ? "" : "/app"}/companies/${node.company_id}`,
      );
    const neighbours = adjacency(nodes, links, filters),
      direct = neighbours.get(id) ?? [],
      related = new Set<string>();
    for (const item of direct) {
      if (byId.get(item.node)!.kind === "company") related.add(item.node);
      else
        for (const next of neighbours.get(item.node) ?? [])
          if (byId.get(next.node)!.kind === "company" && next.node !== id)
            related.add(next.node);
    }
    add(
      "p",
      `${direct.length} direct relationships · ${related.size} connected companies under the current filters.`,
    );
    button("Focus this node", () => focusNode(node));
    if (pathStart && pathStart !== id) {
      add(
        "p",
        path
          ? `Path (${path.edges.length} relationships): ${path.nodes.map((key) => byId.get(key)!.name).join(" → ")}. This is a path, not a direct company relationship.`
          : "No path under the current filters.",
      );
      for (const key of path?.edges ?? []) {
        const edge = links.find((item) => item.id === key)!;
        button(`Inspect path evidence: ${edge.type}`, () => inspectEdge(edge));
      }
    }
    button("Use as path start", () => {
      pathStart = id;
      report("Path start selected. Select another node to inspect a path.");
    });
    button(node.pinned ? "Unpin node" : "Pin node", () => {
      node.pinned = !node.pinned;
      applyFrozen();
      selectNode(id);
    });
    const directHeading = add("h4", "Direct relationships");
    directHeading.className = "graph-inspector-section";
    for (const item of direct)
      button(`${item.edge.type} → ${byId.get(item.node)!.name}`, () =>
        inspectEdge(item.edge),
      );
    if (node.kind === "company" && related.size) {
      const relatedHeading = add(
        "h4",
        "Companies connected through a shared feature",
      );
      relatedHeading.className = "graph-inspector-section";
      for (const key of related)
        button(byId.get(key)!.name, () => {
          pathStart = id;
          selectNode(key);
          focusNode(byId.get(key)!);
        });
    }
    updateHighlights();
    report(`Selected ${node.name}`);
  }
  function fit() {
    const width = container.clientWidth,
      height = container.clientHeight;
    if (!width || !height) return;
    const xs = nodes.map(nodeX),
      ys = nodes.map(nodeY);
    const minX = Math.min(...xs) - 125,
      maxX = Math.max(...xs) + 125,
      minY = Math.min(...ys) - 105,
      maxY = Math.max(...ys) + 105;
    const k = Math.max(
      0.05,
      Math.min(1.2, width / (maxX - minX), height / (maxY - minY)) * 0.9,
    );
    moveCamera(
      d3.zoomIdentity
        .translate(
          width / 2 - ((maxX + minX) / 2) * k,
          height / 2 - ((maxY + minY) / 2) * k,
        )
        .scale(k),
    );
  }
  function moveCamera(transform: d3.ZoomTransform) {
    cameraTarget = transform;
    svg.interrupt();
    if (motionMS)
      svg
        .transition()
        .duration(motionMS)
        .call(zoom.transform, transform)
        .on("end.camera", () => {
          if (cameraTarget === transform) cameraTarget = null;
        });
    else {
      svg.call(zoom.transform, transform);
      cameraTarget = null;
    }
  }
  function focusNode(node: Node) {
    const k = Math.max(0.85, Math.min(1.3, d3.zoomTransform(svg.node()!).k));
    moveCamera(
      d3.zoomIdentity
        .translate(
          container.clientWidth / 2 - nodeX(node) * k,
          container.clientHeight / 2 - nodeY(node) * k,
        )
        .scale(k),
    );
  }
  function restore() {
    cameraTarget = null;
    svg.interrupt();
    selected = selectedEdge = pathStart = null;
    path = null;
    restorePositions(nodes, links, saved);
    // Fit settled coordinates once; an unattended first layout must not drift
    // outside the viewport after Fit has used its earlier coordinates.
    simulation.stop();
    nodes.forEach((node) => {
      node.fx = null;
      node.fy = null;
    });
    if (!saved)
      simulation
        .alpha(1)
        .alphaTarget(0)
        .tick(nodes.length > 120 ? 100 : 160);
    frozen = saved ? saved.frozen !== false : false;
    filters = saved?.filters
      ? (saved.filters.filter((type) =>
          RELATIONSHIPS.includes(type as Relationship),
        ) as Relationship[])
      : [...RELATIONSHIPS];
    onFilters(filters);
    applyFrozen(false);
    updateHighlights();
    const transform = saved?.zoom;
    if (
      transform &&
      [transform.x, transform.y, transform.k].every(Number.isFinite) &&
      transform.k >= 0.05 &&
      transform.k <= 8
    ) {
      svg
        .interrupt()
        .call(
          zoom.transform,
          d3.zoomIdentity
            .translate(transform.x, transform.y)
            .scale(transform.k),
        );
    } else fit();
    if (saved?.selected && byId.has(saved.selected)) selectNode(saved.selected);
    else emptyInspector();
    report(
      saved
        ? "Saved view restored. New nodes were placed near saved neighbours."
        : "No saved view. Initial layout restored.",
    );
  }
  function emptyInspector() {
    inspector.replaceChildren();
    const emblem = add("div", "");
    emblem.className = "graph-inspector-emblem";
    emblem.setAttribute("aria-hidden", "true");
    const artwork = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "svg",
    );
    artwork.setAttribute("viewBox", "0 0 64 64");
    const outline = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "path",
    );
    outline.setAttribute("d", "M32 16L16 44h32z M32 16v30");
    artwork.append(outline);
    for (const [x, y] of [
      [32, 16],
      [16, 44],
      [48, 44],
    ]) {
      const point = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "circle",
      );
      point.setAttribute("cx", String(x));
      point.setAttribute("cy", String(y));
      point.setAttribute("r", "5");
      artwork.append(point);
    }
    emblem.append(artwork);
    add("h3", "Follow the connections");
    add(
      "p",
      "Select a company, person or shared contact to see who is connected and why. Select a line to inspect its source and legal period.",
    );
    add(
      "p",
      "Drag to arrange nodes. Double-click or press P to pin a node. Saved views keep your arrangement.",
    );
  }
  const keydown = (event: KeyboardEvent) => {
    if (event.target !== container) return;
    if (["+", "=", "-"].includes(event.key)) {
      event.preventDefault();
      cameraTarget = null;
      svg.interrupt().call(zoom.scaleBy, event.key === "-" ? 0.8 : 1.25);
    }
    const shifts: Record<string, number[]> = {
      ArrowLeft: [60, 0],
      ArrowRight: [-60, 0],
      ArrowUp: [0, 60],
      ArrowDown: [0, -60],
    };
    if (shifts[event.key]) {
      event.preventDefault();
      cameraTarget = null;
      svg.interrupt();
      const t = d3.zoomTransform(svg.node()!);
      svg.call(
        zoom.translateBy,
        shifts[event.key][0] / t.k,
        shifts[event.key][1] / t.k,
      );
    }
  };
  container.addEventListener("keydown", keydown);
  let previousWidth = container.clientWidth;
  const observer = new ResizeObserver(() => {
    svg.attr(
      "viewBox",
      `0 0 ${container.clientWidth} ${container.clientHeight}`,
    );
    // A desktop transform does not leave the graph off-screen after narrowing.
    if (previousWidth && container.clientWidth < previousWidth * 0.8) fit();
    previousWidth = container.clientWidth;
  });
  observer.observe(container);
  const updateMotion = () => {
    motionMS = decorationAllowed && !motionQuery.matches ? 320 : 0;
    container.dataset.motionActive = String(motionMS > 0);
    if (motionMS && !revealed) {
      revealed = true;
      groups
        .interrupt()
        .attr("opacity", 0.35)
        .transition()
        .duration(460)
        .delay((_, index) => Math.min(index, 8) * 24)
        .attr("opacity", 1);
    }
    if (!motionMS) {
      simulation.stop();
      svg.interrupt();
      groups.interrupt().attr("opacity", 1);
      // Finish the requested camera position without an unattended timer.
      if (cameraTarget) {
        svg.call(zoom.transform, cameraTarget);
        cameraTarget = null;
      }
    }
  };
  const reducedMotion = () => updateMotion();
  motionQuery.addEventListener("change", reducedMotion);
  updateMotion();
  restore();
  updateHighlights();
  return {
    fit,
    restore,
    reset: () => {
      restorePositions(nodes, links, null);
      nodes.forEach((node) => {
        node.pinned = false;
        node.fx = null;
        node.fy = null;
      });
      simulation
        .stop()
        .alpha(1)
        .alphaTarget(0)
        .tick(nodes.length > 120 ? 100 : 160);
      frozen = false;
      applyFrozen(false);
      fit();
      report("Layout reset. Saved view is still available.");
    },
    freeze: () => {
      frozen = !frozen;
      applyFrozen();
    },
    filter: (values) => {
      filters = values;
      path = null;
      selectedEdge = null;
      updateHighlights();
      if (selected) selectNode(selected);
    },
    search: (value) =>
      nodes.filter((node) =>
        `${node.name} ${node.bin ?? ""}`
          .toLocaleLowerCase()
          .includes(value.trim().toLocaleLowerCase()),
      ),
    select: (id) => {
      selectNode(id);
      const node = byId.get(id);
      if (node) focusNode(node);
    },
    clear: () => {
      selected = selectedEdge = pathStart = null;
      path = null;
      emptyInspector();
      updateHighlights();
      report("Selection cleared.");
    },
    collect: () => {
      // Saving during Fit/Focus records the requested view, not a transient frame.
      svg.interrupt();
      if (cameraTarget) {
        svg.call(zoom.transform, cameraTarget);
        cameraTarget = null;
      }
      const t = d3.zoomTransform(svg.node()!);
      return {
        positions: Object.fromEntries(
          nodes.map((node) => [
            node.id,
            { x: nodeX(node), y: nodeY(node), pinned: !!node.pinned },
          ]),
        ),
        zoom: { x: t.x, y: t.y, k: t.k },
        filters,
        selected,
        frozen,
      };
    },
    setSaved: (value) => {
      saved = value;
    },
    setMotion: (allowed) => {
      decorationAllowed = allowed;
      updateMotion();
    },
    destroy: () => {
      simulation.on("tick", null).on("end", null).stop();
      observer.disconnect();
      motionQuery.removeEventListener("change", reducedMotion);
      container.removeEventListener("keydown", keydown);
      svg.interrupt();
      groups.interrupt();
      line.interrupt();
      glowLine.interrupt();
      delete container.dataset.motionActive;
      svg.on(".zoom", null);
      groups.on(".drag", null);
      container.replaceChildren();
      inspector.replaceChildren();
    },
  };
}

export function GraphExplorer({ graph }: { graph: GraphResponse }) {
  const { user, csrfToken, loading: sessionLoading } = useSession();
  const { ref: workspace, active: decorationActive } =
    useDecorationActive<HTMLElement>();
  const canvas = useRef<HTMLDivElement>(null);
  const motionActive = useRef(decorationActive);
  motionActive.current = decorationActive;
  const inspector = useRef<HTMLDivElement>(null),
    controller = useRef<Controller | null>(null);
  const revision = useRef(0),
    saveAbort = useRef<AbortController | null>(null);
  const viewReadAbort = useRef<AbortController | null>(null),
    viewReadSequence = useRef(0);
  const [status, setStatus] = useState("Loading saved view…"),
    [ready, setReady] = useState(false),
    [saving, setSaving] = useState(false);
  const [privateViewReady, setPrivateViewReady] = useState(false),
    [readingView, setReadingView] = useState(false),
    [saveFeedback, setSaveFeedback] = useState<{
      state: "success" | "error" | "loading" | "info";
      message: string;
      retryView?: boolean;
    } | null>(null);
  const [filters, setFilters] = useState<Relationship[]>([...RELATIONSHIPS]),
    [frozen, setFrozen] = useState(false),
    [query, setQuery] = useState(""),
    [matches, setMatches] = useState<Node[]>([]);
  const authenticated = user.role !== "anonymous";
  useEffect(() => {
    setReady(false);
    setSaving(false);
    setPrivateViewReady(false);
    setReadingView(false);
    setSaveFeedback(null);
    if (
      sessionLoading ||
      !canvas.current ||
      !inspector.current ||
      !graph.graph.nodes.length
    )
      return;
    const abort = new AbortController();
    viewReadAbort.current = abort;
    const readSequence = ++viewReadSequence.current;
    let disposed = false;
    setReady(false);
    setSaving(false);
    setQuery("");
    setMatches([]);
    setStatus("Loading saved view…");
    setReadingView(authenticated);
    const mount = async () => {
      let payload: ViewPayload | null = null,
        browserViewLoaded = false,
        loadError = "",
        fetchedRevision = 0;
      if (authenticated) {
        try {
          const view = await getJson<GraphView>(
            queryPath(`clusters/${graph.cluster}/view/`, {
              version: graph.version,
            }),
            abort.signal,
          );
          if (!Number.isSafeInteger(view.revision) || view.revision < 0)
            throw new Error(
              "The saved view revision could not be read. Try again.",
            );
          payload = sanitizeView(view.payload);
          fetchedRevision = view.revision;
          // A successful empty account view may start from the guest layout.
          // Copying it to the account still requires an explicit Save view.
          if (view.payload === null) {
            try {
              const browserView = sanitizeView(
                JSON.parse(
                  localStorage.getItem(graphStorageKey(graph.cluster)) ??
                    "null",
                ),
              );
              if (browserView && Object.keys(browserView).length) {
                payload = browserView;
                browserViewLoaded = true;
              }
            } catch {
              /* An optional browser layout must not block an account view. */
            }
          }
        } catch (error) {
          if (abort.signal.aborted) return;
          loadError =
            error instanceof Error
              ? error.message
              : "Personal view is unavailable.";
        }
      } else {
        try {
          payload = sanitizeView(
            JSON.parse(
              localStorage.getItem(graphStorageKey(graph.cluster)) ?? "null",
            ),
          );
        } catch {
          loadError =
            "Browser storage is unavailable. The initial layout is shown.";
        }
      }
      if (
        disposed ||
        readSequence !== viewReadSequence.current ||
        !canvas.current ||
        !inspector.current
      )
        return;
      revision.current = fetchedRevision;
      controller.current = mountGraph(
        canvas.current,
        inspector.current,
        graph,
        payload,
        setStatus,
        setFilters,
        setFrozen,
        motionActive.current,
      );
      setReady(true);
      setReadingView(false);
      setPrivateViewReady(authenticated && !loadError);
      if (browserViewLoaded) {
        const message =
          "Browser view loaded. Save view to copy it to your account.";
        setStatus(message);
        setSaveFeedback({ state: "info", message });
      }
      if (loadError) {
        const message =
          loadError +
          (authenticated ? " Retry the saved view before saving." : "");
        setStatus(message);
        setSaveFeedback({ state: "error", message });
      }
    };
    void mount();
    return () => {
      disposed = true;
      viewReadSequence.current++;
      abort.abort();
      viewReadAbort.current?.abort();
      saveAbort.current?.abort();
      controller.current?.destroy();
      controller.current = null;
    };
  }, [graph, authenticated, user.id, sessionLoading]);

  useEffect(() => {
    controller.current?.setMotion(decorationActive);
  }, [decorationActive]);

  const retrySavedView = async () => {
    if (!authenticated || !controller.current || readingView || saving) return;
    const ownedController = controller.current;
    const request = ++viewReadSequence.current;
    viewReadAbort.current?.abort();
    const abort = new AbortController();
    viewReadAbort.current = abort;
    setReadingView(true);
    setPrivateViewReady(false);
    setSaveFeedback({
      state: "loading",
      message: "Reading your saved account view…",
    });
    try {
      const view = await getJson<GraphView>(
        queryPath("clusters/" + graph.cluster + "/view/", {
          version: graph.version,
        }),
        abort.signal,
      );
      if (
        abort.signal.aborted ||
        request !== viewReadSequence.current ||
        controller.current !== ownedController
      )
        return;
      if (!Number.isSafeInteger(view.revision) || view.revision < 0)
        throw new Error(
          "The saved view revision could not be read. Try again.",
        );
      revision.current = view.revision;
      ownedController.setSaved(sanitizeView(view.payload));
      setPrivateViewReady(true);
      const message = view.payload
        ? "Latest account view loaded. Your current arrangement is unchanged. Save it or choose Restore saved view."
        : "No account view has been saved yet. Your current arrangement is unchanged and can now be saved.";
      setSaveFeedback({ state: "info", message });
      setStatus(message);
    } catch (error) {
      if (!abort.signal.aborted && request === viewReadSequence.current) {
        const message =
          error instanceof Error
            ? error.message
            : "Your saved view could not be loaded. Try again.";
        setSaveFeedback({ state: "error", message });
        setStatus(message);
      }
    } finally {
      if (!abort.signal.aborted && request === viewReadSequence.current)
        setReadingView(false);
    }
  };

  const save = async () => {
    if (
      !controller.current ||
      !ready ||
      saving ||
      graph.historical ||
      (saveAbort.current && !saveAbort.current.signal.aborted) ||
      (authenticated && !privateViewReady)
    )
      return;
    const ownedController = controller.current;
    const payload = ownedController.collect();
    if (!authenticated) {
      try {
        localStorage.setItem(
          graphStorageKey(graph.cluster),
          JSON.stringify(payload),
        );
        ownedController.setSaved(payload);
        const message =
          "View saved in this browser. Sign in to save across devices.";
        setStatus(message);
        setSaveFeedback({ state: "success", message });
      } catch {
        const message = "View was not saved. Browser storage is unavailable.";
        setStatus(message);
        setSaveFeedback({ state: "error", message });
      }
      return;
    }
    if (!csrfToken || !graph.snapshot_id || !graph.graph_hash) {
      const message =
        "Session or graph information is unavailable. Reload before saving.";
      setStatus(message);
      setSaveFeedback({ state: "error", message });
      return;
    }
    setSaving(true);
    setSaveFeedback({
      state: "loading",
      message: "Saving your personal view…",
    });
    const abort = new AbortController();
    saveAbort.current = abort;
    try {
      const result = await apiFetch<GraphView>(
        "clusters/" + graph.cluster + "/view/",
        {
          method: "PUT",
          csrfToken,
          signal: abort.signal,
          body: {
            snapshot_id: graph.snapshot_id,
            graph_hash: graph.graph_hash,
            revision: revision.current,
            payload,
          },
        },
      );
      if (abort.signal.aborted || controller.current !== ownedController)
        return;
      if (
        !Number.isSafeInteger(result.revision) ||
        result.revision < 0 ||
        !result.payload
      )
        throw new ApiError(
          "The server did not confirm the saved view. Reload the saved account view before trying again.",
          200,
          "invalid_response",
        );
      revision.current = result.revision;
      ownedController.setSaved(result.payload);
      setStatus("Personal view saved.");
      setSaveFeedback({
        state: "success",
        message:
          "View saved to your account. Restore saved view returns to this arrangement.",
      });
    } catch (error) {
      if (!abort.signal.aborted && controller.current === ownedController) {
        const conflict = error instanceof ApiError && error.status === 409;
        const graphChanged =
          conflict && /current graph changed/i.test(error.message);
        if (
          error instanceof ApiError &&
          (conflict ||
            error.status === 403 ||
            error.code === "invalid_response")
        )
          setPrivateViewReady(false);
        const message = graphChanged
          ? "The current graph changed. Reload this page to open the latest graph before saving."
          : conflict
            ? "Graph or view changed in another tab. Reload the saved account view before saving."
            : error instanceof ApiError && error.status === 403
              ? "View was not saved. Sign in again or reload the page before saving."
              : error instanceof Error
                ? error.message
                : "View could not be saved.";
        setStatus(message);
        setSaveFeedback({
          state: "error",
          message,
          retryView:
            !graphChanged &&
            !(error instanceof ApiError && error.status === 403),
        });
      }
    } finally {
      if (saveAbort.current === abort) saveAbort.current = null;
      if (!abort.signal.aborted && controller.current === ownedController)
        setSaving(false);
    }
  };
  const updateSearch = (value: string) => {
    setQuery(value);
    setMatches(
      value.trim()
        ? (controller.current?.search(value) ?? []).slice(0, 20)
        : [],
    );
  };
  return (
    <section
      className="panel graph-workspace"
      ref={workspace}
      aria-label="Relationship explorer"
      data-motion-active={decorationActive}
    >
      <div className="graph-heading">
        <div>
          <span className="eyebrow">Relationship explorer</span>
          <TechHeading as="h2" text="Network evidence" />
        </div>
        <div className="graph-metrics">
          {(
            [
              ["company", "company", "companies"],
              ["person", "person", "people"],
              ["contact", "contact", "contacts"],
            ] as const
          ).map(([kind, singular, plural]) => {
            const count = graph.graph.nodes.filter(
              (node) => node.kind === kind,
            ).length;
            return (
              <span key={kind}>
                <strong>{count}</strong> {count === 1 ? singular : plural}
              </span>
            );
          })}
          <span>
            <strong>{graph.graph.links.length}</strong>{" "}
            {graph.graph.links.length === 1 ? "relationship" : "relationships"}
          </span>
        </div>
      </div>
      <div className="graph-toolbar">
        <label className="field graph-search">
          <span>Find a node</span>
          <div className="graph-search-input">
            <MagnifyingGlassIcon />
            <input
              value={query}
              onChange={(event) => updateSearch(event.target.value)}
              placeholder="Company, BIN, person or contact"
              disabled={!ready}
            />
          </div>
        </label>
        <button
          className="button button-quiet"
          disabled={!ready}
          onClick={() => controller.current?.fit()}
        >
          <EnterFullScreenIcon />
          Fit
        </button>
        <button
          className="button button-quiet"
          disabled={!ready}
          onClick={() => controller.current?.reset()}
        >
          <ResetIcon />
          Reset layout
        </button>
        <button
          className="button button-quiet"
          disabled={!ready}
          onClick={() => controller.current?.restore()}
        >
          <ReloadIcon />
          Restore saved view
        </button>
        <button
          className="button"
          disabled={
            !ready ||
            saving ||
            readingView ||
            graph.historical ||
            (authenticated && !privateViewReady)
          }
          aria-describedby={saveFeedback ? "graph-save-feedback" : undefined}
          aria-busy={saving}
          onClick={() => void save()}
          title={
            graph.historical
              ? "Open the current graph before saving a view"
              : undefined
          }
        >
          <BookmarkIcon />
          {saving ? "Saving…" : "Save view"}
        </button>
        <button
          className="button button-quiet"
          disabled={!ready}
          aria-pressed={frozen}
          onClick={() => controller.current?.freeze()}
        >
          {frozen ? <LockOpen1Icon /> : <LockClosedIcon />}
          {frozen ? "Resume layout" : "Freeze positions"}
        </button>
      </div>
      {saveFeedback && (
        <div
          id="graph-save-feedback"
          className="graph-save-feedback"
          data-state={saveFeedback.state}
          role={saveFeedback.state === "error" ? "alert" : undefined}
          aria-live={saveFeedback.state === "error" ? "assertive" : "polite"}
          aria-atomic="true"
        >
          <span>{saveFeedback.message}</span>
          {authenticated &&
            saveFeedback.retryView !== false &&
            !privateViewReady &&
            ready &&
            !graph.historical && (
              <button
                className="button button-quiet"
                disabled={readingView || saving}
                onClick={() => void retrySavedView()}
              >
                <ReloadIcon />
                {readingView ? "Reading view…" : "Reload saved account view"}
              </button>
            )}
        </div>
      )}
      {query.trim() && (
        <div className="graph-results" aria-label="Matching nodes">
          {matches.length ? (
            matches.map((node) => (
              <button
                key={node.id}
                className="button button-quiet"
                onClick={() => controller.current?.select(node.id)}
              >
                {node.kind}: {node.name}
              </button>
            ))
          ) : (
            <p>No matching nodes.</p>
          )}
          {matches.length === 20 && (
            <small>Up to 20 matching nodes shown.</small>
          )}
        </div>
      )}
      <fieldset className="graph-filters">
        <legend>Relationships</legend>
        {RELATIONSHIPS.map((type) => (
          <label className={`filter-${type}`} key={type}>
            <input
              type="checkbox"
              checked={filters.includes(type)}
              disabled={!ready}
              onChange={(event) => {
                const next = event.target.checked
                  ? [...filters, type]
                  : filters.filter((value) => value !== type);
                setFilters(next);
                controller.current?.filter(next);
              }}
            />
            <span className="graph-dot" />
            {type[0].toUpperCase() + type.slice(1)}
          </label>
        ))}
      </fieldset>
      <div className="graph-legend">
        <span>
          <span className="legend-shape legend-company" />
          Company
        </span>
        <span>
          <span className="legend-shape legend-person" />
          Verified person
        </span>
        <span>
          <span className="legend-shape legend-contact" />
          Shared contact
        </span>
        <span>
          <span className="legend-link" />
          Role
        </span>
        <span>
          <span className="legend-link legend-weak" />
          Weak contact
        </span>
        <span>Click to focus · drag to arrange · scroll to zoom</span>
      </div>
      {graph.graph.nodes.length ? (
        <div className="graph-panels">
          <div className="graph-stage">
            <div
              className="graph-canvas"
              ref={canvas}
              tabIndex={0}
              aria-label="Interactive saved graph. Use arrow keys to pan and plus or minus to zoom."
            />
            <div className="graph-map-caption" aria-hidden="true">
              <span>
                <span className="graph-caption-mark" />
                Saved network
              </span>
              <span>Version {graph.version ?? "—"}</span>
            </div>
            <span className="graph-map-corner corner-top" aria-hidden="true" />
            <span
              className="graph-map-corner corner-bottom"
              aria-hidden="true"
            />
          </div>
          <aside className="graph-inspector">
            <span className="eyebrow">Evidence panel</span>
            <div ref={inspector} />
          </aside>
        </div>
      ) : (
        <div className="empty-state">
          <h3>No saved graph</h3>
          <p>This group has no nodes in the selected version.</p>
        </div>
      )}
      <p className="graph-status" role="status">
        {graph.graph.nodes.length ? status : "No nodes in this saved version."}
      </p>
      <div className="graph-bottom">
        <p>
          A path through a shared person or contact is different from a direct
          company relationship. Confidence describes evidence strength, not a
          probability of wrongdoing. Unknown legal periods remain unconfirmed.
        </p>
        <button
          className="button button-quiet"
          disabled={!ready}
          onClick={() => {
            controller.current?.clear();
            setQuery("");
            setMatches([]);
          }}
        >
          <Cross2Icon />
          Clear selection
        </button>
      </div>
    </section>
  );
}
