import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MotionPreferences } from "../MotionPreferences";
import { EvidenceMeter } from "./EvidenceMeter";
import { SpotlightSurface, useSpotlight } from "./SpotlightSurface";

class TestPointerEvent extends MouseEvent {
  pointerType: string;
  constructor(type: string, init: PointerEventInit = {}) {
    super(type, init);
    this.pointerType = init.pointerType ?? "mouse";
  }
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  localStorage.clear();
  delete document.documentElement.dataset.motion;
});

function SpotlightLink() {
  const { active, surfaceProps } = useSpotlight<HTMLAnchorElement>();
  return (
    <a {...surfaceProps} href="/companies" data-active={active}>
      Open companies
    </a>
  );
}

describe("decorative spotlight", () => {
  it("preserves the native link and keyboard focus without adding a tab stop", () => {
    render(
      <SpotlightSurface data-testid="surface">
        <SpotlightLink />
      </SpotlightSurface>,
    );
    const link = screen.getByRole("link", { name: "Open companies" });
    fireEvent.focus(link);
    expect(link).toHaveAttribute("data-active", "true");
    expect(link).toHaveAttribute("href", "/companies");
    expect(screen.getByTestId("surface")).not.toHaveAttribute("tabindex");
    fireEvent.blur(link, { relatedTarget: document.body });
    expect(link).toHaveAttribute("data-active", "false");
  });

  it("batches pointer updates and cancels its pending frame on unmount", () => {
    vi.stubGlobal("PointerEvent", TestPointerEvent);
    const request = vi.fn(() => 71);
    const cancel = vi.fn();
    vi.stubGlobal("requestAnimationFrame", request);
    vi.stubGlobal("cancelAnimationFrame", cancel);
    const { unmount } = render(<SpotlightLink />);
    const link = screen.getByRole("link");
    fireEvent.pointerMove(link, { clientX: 20, clientY: 10 });
    fireEvent.pointerMove(link, { clientX: 30, clientY: 20 });
    expect(request).toHaveBeenCalledTimes(1);
    unmount();
    expect(cancel).toHaveBeenCalledWith(71);
  });

  it("does not schedule motion when the user has disabled animations", () => {
    vi.stubGlobal("PointerEvent", TestPointerEvent);
    const request = vi.fn(() => 72);
    vi.stubGlobal("requestAnimationFrame", request);
    localStorage.setItem("iz2.motion-enabled.v1", "false");
    render(
      <MotionPreferences>
        <SpotlightLink />
      </MotionPreferences>,
    );
    const link = screen.getByRole("link");
    fireEvent.pointerMove(link, { clientX: 20, clientY: 10 });
    expect(request).not.toHaveBeenCalled();
    expect(link).toHaveAttribute("data-spotlight-motion", "off");
  });
});

describe("saved evidence coverage", () => {
  it("represents confirmed zero coverage as a meter with the saved denominator", () => {
    render(
      <EvidenceMeter label="Identity verification" value={0} total={768} />,
    );
    expect(
      screen.getByRole("meter", { name: "Identity verification" }),
    ).toHaveAttribute("aria-valuenow", "0");
    expect(screen.getByRole("meter")).toHaveAttribute("aria-valuemax", "768");
    expect(screen.getByRole("meter")).toHaveAttribute(
      "aria-valuetext",
      "0 of 768 records",
    );
  });

  it("distinguishes unavailable coverage and an empty denominator from a measured zero", () => {
    const { rerender } = render(
      <EvidenceMeter label="Identity verification" value={null} total={null} />,
    );
    expect(screen.queryByRole("meter")).not.toBeInTheDocument();
    expect(screen.getByText("Not available")).toBeInTheDocument();
    rerender(
      <EvidenceMeter label="Identity verification" value={0} total={0} />,
    );
    expect(screen.queryByRole("meter")).not.toBeInTheDocument();
    expect(screen.getByText("No saved records to assess")).toBeInTheDocument();
  });
});
