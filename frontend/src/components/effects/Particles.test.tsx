import { StrictMode } from "react";
import { act, fireEvent, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MotionPreferences } from "../MotionPreferences";
import Particles from "./Particles";

const gpu = vi.hoisted(() => ({
  renders: vi.fn(),
  loseContext: vi.fn(),
  geometries: [] as Array<{ remove: ReturnType<typeof vi.fn> }>,
  programs: [] as Array<{
    remove: ReturnType<typeof vi.fn>;
    uniforms: Record<string, { value: unknown }>;
  }>,
  rendererCount: 0,
}));

vi.mock("ogl", () => ({
  Renderer: class {
    dpr: number;
    gl: {
      canvas: HTMLCanvasElement;
      clearColor: ReturnType<typeof vi.fn>;
      getExtension: () => { loseContext: ReturnType<typeof vi.fn> };
      POINTS: number;
    };
    constructor(options: { canvas: HTMLCanvasElement; dpr: number }) {
      gpu.rendererCount++;
      this.dpr = options.dpr;
      this.gl = {
        canvas: options.canvas,
        clearColor: vi.fn(),
        getExtension: () => ({ loseContext: gpu.loseContext }),
        POINTS: 0,
      };
    }
    setSize(width: number, height: number) {
      this.gl.canvas.width = Math.round(width * this.dpr);
      this.gl.canvas.height = Math.round(height * this.dpr);
    }
    render = gpu.renders;
  },
  Camera: class {
    position = { set: vi.fn() };
    perspective = vi.fn();
  },
  Geometry: class {
    remove = vi.fn();
    constructor() {
      gpu.geometries.push(this);
    }
  },
  Program: class {
    remove = vi.fn();
    uniforms: Record<string, { value: unknown }>;
    constructor(
      _context: unknown,
      options: { uniforms: Record<string, { value: unknown }> },
    ) {
      this.uniforms = options.uniforms;
      gpu.programs.push(this);
    }
  },
  Mesh: class {
    position = { x: 0, y: 0 };
    rotation = { x: 0, y: 0, z: 0 };
  },
}));

let frames: Map<number, FrameRequestCallback>;
let nextFrame: number;
let hidden: boolean;

beforeEach(() => {
  gpu.renders.mockClear();
  gpu.loseContext.mockClear();
  gpu.geometries.length = 0;
  gpu.programs.length = 0;
  gpu.rendererCount = 0;
  frames = new Map();
  nextFrame = 1;
  hidden = false;
  vi.spyOn(document, "hidden", "get").mockImplementation(() => hidden);
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(
    () =>
      ({
        getExtension: () => ({ loseContext: gpu.loseContext }),
      }) as unknown as WebGLRenderingContext,
  );
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

describe("Particles ownership and motion", () => {
  it("owns one RAF and releases both StrictMode contexts, geometry and programs", () => {
    const { container, unmount } = render(
      <StrictMode>
        <Particles />
      </StrictMode>,
    );
    expect(gpu.rendererCount).toBe(2);
    expect(container.querySelectorAll("canvas")).toHaveLength(1);
    expect(frames.size).toBe(1);
    expect(gpu.geometries[0].remove).toHaveBeenCalledOnce();
    unmount();
    expect(frames.size).toBe(0);
    expect(
      gpu.geometries.every(
        (geometry) => geometry.remove.mock.calls.length === 1,
      ),
    ).toBe(true);
    expect(
      gpu.programs.every((program) => program.remove.mock.calls.length === 1),
    ).toBe(true);
    expect(gpu.loseContext).toHaveBeenCalledTimes(2);
  });

  it("pauses a hidden tab and resumes without adding hidden time", () => {
    render(<Particles />);
    step(0);
    step(100);
    const beforePause = gpu.programs[0].uniforms.uTime.value;
    const twinkleBeforePause = gpu.programs[0].uniforms.uTwinkleTime.value;
    hidden = true;
    fireEvent(document, new Event("visibilitychange"));
    expect(frames.size).toBe(0);
    hidden = false;
    fireEvent(document, new Event("visibilitychange"));
    step(9000);
    expect(gpu.programs[0].uniforms.uTime.value).toBe(beforePause);
    expect(gpu.programs[0].uniforms.uTwinkleTime.value).toBe(
      twinkleBeforePause,
    );
    expect(frames.size).toBe(1);
  });

  it("keeps twinkling when particle drift is set to zero without another loop", () => {
    render(<Particles speed={0} />);
    step(0);
    step(100);
    expect(gpu.programs[0].uniforms.uTime.value).toBe(0);
    expect(gpu.programs[0].uniforms.uTwinkleTime.value).toBeCloseTo(0.1);
    expect(frames.size).toBe(1);
  });

  it("rebuilds changed GPU configuration while retaining one active loop", () => {
    const { container, rerender } = render(<Particles />);
    expect(frames.size).toBe(1);
    rerender(<Particles particleCount={220} />);
    expect(gpu.rendererCount).toBe(2);
    expect(gpu.geometries[0].remove).toHaveBeenCalledOnce();
    expect(gpu.programs[0].remove).toHaveBeenCalledOnce();
    expect(container.querySelectorAll("canvas")).toHaveLength(1);
    expect(frames.size).toBe(1);
    step(0);
    expect(frames.size).toBe(1);
  });

  it("renders a static field with no RAF when motion is disabled", () => {
    localStorage.setItem("iz2.motion-enabled.v1", "false");
    const { container } = render(
      <MotionPreferences>
        <Particles />
      </MotionPreferences>,
    );
    expect(container.querySelector(".iz2-particles")).toHaveAttribute(
      "data-mode",
      "webgl",
    );
    expect(gpu.renders).toHaveBeenCalledOnce();
    expect(frames.size).toBe(0);
  });

  it("falls back to a CSS field and stops drawing after context loss", () => {
    const { container } = render(<Particles />);
    const canvas = container.querySelector("canvas")!;
    const event = new Event("webglcontextlost", { cancelable: true });
    fireEvent(canvas, event);
    expect(event.defaultPrevented).toBe(true);
    expect(container.querySelector(".iz2-particles")).toHaveAttribute(
      "data-mode",
      "fallback",
    );
    expect(container.querySelector("canvas")).toBeNull();
    expect(
      container.querySelectorAll(".iz2-particles-fallback > i"),
    ).toHaveLength(240);
    expect(frames.size).toBe(0);
    expect(gpu.geometries[0].remove).toHaveBeenCalledOnce();
    expect(gpu.programs[0].remove).toHaveBeenCalledOnce();
  });

  it("uses the CSS fallback without constructing OGL when WebGL is unsupported", () => {
    vi.mocked(HTMLCanvasElement.prototype.getContext).mockReturnValue(null);
    const { container } = render(<Particles />);
    expect(container.querySelector(".iz2-particles")).toHaveAttribute(
      "data-mode",
      "fallback",
    );
    expect(
      container.querySelectorAll(".iz2-particles-fallback > i"),
    ).toHaveLength(240);
    expect(gpu.rendererCount).toBe(0);
    expect(frames.size).toBe(0);
  });
});
