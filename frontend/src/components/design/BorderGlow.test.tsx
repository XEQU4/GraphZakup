import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Link, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MotionPreferences, useMotionPreferences } from "../MotionPreferences";
import { BorderGlow, useBorderGlow } from "./BorderGlow";

let frames: Map<number, FrameRequestCallback>;
let nextFrame: number;
let hidden: boolean;

beforeEach(() => {
  frames = new Map();
  nextFrame = 1;
  hidden = false;
  vi.spyOn(document, "hidden", "get").mockImplementation(() => hidden);
  vi.stubGlobal("PointerEvent", MouseEvent);
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
    const id = nextFrame++;
    frames.set(id, callback);
    return id;
  });
  vi.stubGlobal("cancelAnimationFrame", (id: number) => frames.delete(id));
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  localStorage.clear();
  delete document.documentElement.dataset.motion;
});

function Card() {
  const { surfaceProps, decoration } = useBorderGlow<HTMLAnchorElement>();
  return (
    <Link
      {...surfaceProps}
      to="/clusters/saved"
      className={surfaceProps.className + " saved-card"}
    >
      {decoration}Open saved group
    </Link>
  );
}
function Location() {
  return <output aria-label="Current route">{useLocation().pathname}</output>;
}
function MotionToggle() {
  const { toggle } = useMotionPreferences();
  return <button onClick={toggle}>Toggle motion</button>;
}
function moveNearEdge(element: HTMLElement) {
  vi.spyOn(element, "getBoundingClientRect").mockReturnValue({
    x: 10,
    y: 20,
    left: 10,
    top: 20,
    right: 210,
    bottom: 120,
    width: 200,
    height: 100,
    toJSON: () => ({}),
  });
  fireEvent.pointerMove(element, { clientX: 209, clientY: 23 });
}

describe("Border Glow native surfaces", () => {
  it("keeps link navigation, keyboard focus and decorative accessibility", () => {
    const { container } = render(
      <MemoryRouter>
        <Card />
        <Location />
      </MemoryRouter>,
    );
    const link = screen.getByRole("link", { name: "Open saved group" });
    expect(link).toHaveAttribute("href", "/clusters/saved");
    act(() => link.focus());
    expect(link).toHaveFocus();
    expect(link).toHaveAttribute("data-border-glow-focus", "true");
    expect(frames.size).toBe(0);
    expect(
      container.querySelector(".iz2-border-glow__decoration"),
    ).toHaveAttribute("aria-hidden", "true");
    fireEvent.click(link);
    expect(screen.getByLabelText("Current route")).toHaveTextContent(
      "/clusters/saved",
    );
  });

  it("cancels queued pointer work on leave and unmount", () => {
    const { unmount } = render(
      <MemoryRouter>
        <Card />
      </MemoryRouter>,
    );
    const link = screen.getByRole("link");
    moveNearEdge(link);
    expect(frames.size).toBe(1);
    fireEvent.pointerLeave(link);
    expect(frames.size).toBe(0);
    expect(link.style.getPropertyValue("--border-glow-edge")).toBe("0");
    moveNearEdge(link);
    expect(frames.size).toBe(1);
    unmount();
    expect(frames.size).toBe(0);
  });

  it("cancels work when the document becomes hidden or motion is disabled", () => {
    render(
      <MotionPreferences>
        <MemoryRouter>
          <Card />
          <MotionToggle />
        </MemoryRouter>
      </MotionPreferences>,
    );
    const link = screen.getByRole("link");
    moveNearEdge(link);
    expect(frames.size).toBe(1);
    hidden = true;
    act(() => document.dispatchEvent(new Event("visibilitychange")));
    expect(frames.size).toBe(0);
    expect(link).toHaveAttribute("data-border-glow-active", "false");
    hidden = false;
    act(() => document.dispatchEvent(new Event("visibilitychange")));
    moveNearEdge(link);
    expect(frames.size).toBe(1);
    fireEvent.click(screen.getByRole("button", { name: "Toggle motion" }));
    expect(frames.size).toBe(0);
    expect(link.style.getPropertyValue("--border-glow-edge")).toBe("0");
    expect(link).toHaveAttribute("data-border-glow-active", "false");
  });

  it("adds no tab stop or role to an About section", () => {
    render(
      <BorderGlow as="section" aria-labelledby="about-heading">
        <h2 id="about-heading">About IZ2</h2>
        <a href="/app/companies">Browse companies</a>
      </BorderGlow>,
    );
    const section = screen.getByRole("region", { name: "About IZ2" });
    expect(section).not.toHaveAttribute("tabindex");
    expect(screen.getAllByRole("link")).toHaveLength(1);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
