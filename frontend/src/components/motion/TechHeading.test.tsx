import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TechHeading } from "./TechHeading";

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("TechHeading reveal completion", () => {
  it("finishes even when hovering the final glyph cancels its CSS animation", () => {
    const { container } = render(<TechHeading as="h1" text="HELLO" />);
    const heading = screen.getByRole("heading", { name: "HELLO" });
    const glyphs = container.querySelectorAll(".tech-heading__glyph");
    fireEvent.pointerEnter(glyphs[glyphs.length - 1]);
    expect(glyphs[glyphs.length - 1]).toHaveAttribute("data-selected", "true");
    expect(heading).toHaveAttribute("data-revealed", "false");
    act(() => vi.advanceTimersByTime(800));
    expect(heading).toHaveAttribute("data-revealed", "true");
  });

  it("cancels pending completion when the document becomes hidden", () => {
    let hidden = false;
    vi.spyOn(document, "hidden", "get").mockImplementation(() => hidden);
    render(<TechHeading as="h1" text="HELLO" />);
    const heading = screen.getByRole("heading", { name: "HELLO" });
    hidden = true;
    fireEvent(document, new Event("visibilitychange"));
    act(() => vi.advanceTimersByTime(2000));
    expect(heading).toHaveAttribute("data-revealed", "false");
    hidden = false;
    fireEvent(document, new Event("visibilitychange"));
    act(() => vi.advanceTimersByTime(800));
    expect(heading).toHaveAttribute("data-revealed", "true");
  });

  it("does not retain a completion timer after unmount", () => {
    const { unmount } = render(<TechHeading as="h1" text="HELLO" />);
    expect(vi.getTimerCount()).toBeGreaterThan(0);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
});
