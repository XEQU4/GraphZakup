import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MotionPreferences, useMotionPreferences } from "../MotionPreferences";
import CountUp from "./CountUp";

let frames: Map<number, FrameRequestCallback>;
let nextFrame: number;
let hidden: boolean;

beforeEach(() => {
  frames = new Map();
  nextFrame = 1;
  hidden = false;
  vi.spyOn(document, "hidden", "get").mockImplementation(() => hidden);
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

function step(time: number) {
  act(() => {
    const pending = [...frames.values()];
    frames.clear();
    pending.forEach((callback) => callback(time));
  });
}

function visual(container: HTMLElement) {
  return container.querySelector("[data-countup-visual]")!;
}

function PauseMotion() {
  const { toggle } = useMotionPreferences();
  return <button onClick={toggle}>Toggle motion</button>;
}

describe("saved integer CountUp", () => {
  it("keeps the exact final count accessible while its decorative value animates", () => {
    const { container } = render(<CountUp value={100} duration={1} />);
    expect(container.querySelector(".sr-only")).toHaveTextContent("100");
    expect(visual(container)).toHaveAttribute("aria-hidden", "true");
    step(0);
    step(500);
    expect(visual(container)).toHaveTextContent("88");
    expect(container.querySelector(".sr-only")).toHaveTextContent("100");
    step(1000);
    expect(visual(container)).toHaveTextContent("100");
    expect(frames.size).toBe(0);
  });

  it("does not show an invented zero for unknown or invalid values", () => {
    const { container, rerender } = render(<CountUp value={undefined} />);
    expect(visual(container)).toHaveTextContent("—");
    expect(frames.size).toBe(0);
    rerender(<CountUp value={1.2} />);
    expect(visual(container)).toHaveTextContent("—");
    rerender(<CountUp value={-1} />);
    expect(visual(container)).toHaveTextContent("—");
  });

  it("fences an old animation when the saved target changes", () => {
    const { container, rerender } = render(
      <CountUp value={100} duration={1} />,
    );
    step(0);
    step(500);
    rerender(<CountUp value={12} duration={1} />);
    expect(container.querySelector(".sr-only")).toHaveTextContent("12");
    step(600);
    step(1600);
    expect(visual(container)).toHaveTextContent("12");
    expect(frames.size).toBe(0);
  });

  it("settles to the final count immediately when motion is switched off", () => {
    const { container } = render(
      <MotionPreferences>
        <CountUp value={777} duration={1} />
        <PauseMotion />
      </MotionPreferences>,
    );
    step(0);
    fireEvent.click(screen.getByRole("button", { name: "Toggle motion" }));
    expect(visual(container)).toHaveTextContent("777");
    expect(frames.size).toBe(0);
    fireEvent.click(screen.getByRole("button", { name: "Toggle motion" }));
    expect(visual(container)).toHaveTextContent("777");
    expect(frames.size).toBe(0);
  });

  it("renders the saved count directly when the system requests reduced motion", () => {
    vi.spyOn(window, "matchMedia").mockImplementation((query) => ({
      matches: true,
      media: query,
      onchange: null,
      addListener() {},
      removeListener() {},
      addEventListener() {},
      removeEventListener() {},
      dispatchEvent: () => false,
    }));
    const { container } = render(
      <MotionPreferences>
        <CountUp value={777} />
      </MotionPreferences>,
    );
    expect(visual(container)).toHaveTextContent("777");
    expect(frames.size).toBe(0);
  });

  it("pauses in a hidden document and resumes without counting hidden time", () => {
    const { container } = render(<CountUp value={100} duration={1} />);
    step(0);
    step(200);
    const beforePause = visual(container).textContent;
    hidden = true;
    fireEvent(document, new Event("visibilitychange"));
    expect(frames.size).toBe(0);
    hidden = false;
    fireEvent(document, new Event("visibilitychange"));
    step(9000);
    expect(visual(container).textContent).toBe(beforePause);
    step(9800);
    expect(visual(container)).toHaveTextContent("100");
  });

  it("waits for the viewport and disconnects on unmount", () => {
    let intersect: IntersectionObserverCallback | undefined;
    const disconnect = vi.fn();
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        constructor(callback: IntersectionObserverCallback) {
          intersect = callback;
        }
        observe() {}
        disconnect = disconnect;
      },
    );
    const { container, unmount } = render(<CountUp value={500} duration={1} />);
    expect(frames.size).toBe(0);
    act(() =>
      intersect?.(
        [{ isIntersecting: true } as IntersectionObserverEntry],
        {} as IntersectionObserver,
      ),
    );
    step(0);
    step(300);
    const paused = visual(container).textContent;
    act(() =>
      intersect?.(
        [{ isIntersecting: false } as IntersectionObserverEntry],
        {} as IntersectionObserver,
      ),
    );
    expect(frames.size).toBe(0);
    expect(visual(container).textContent).toBe(paused);
    unmount();
    expect(disconnect).toHaveBeenCalledOnce();
  });

  it("does not restart a completed count during unrelated re-renders", () => {
    const { container, rerender } = render(
      <CountUp value={500} duration={1} />,
    );
    step(0);
    step(1000);
    rerender(<CountUp value={500} duration={1} className="stat-number" />);
    expect(visual(container)).toHaveTextContent("500");
    expect(frames.size).toBe(0);
  });
});
