// React Bits Particles, Copyright (c) 2026 David Haz. MIT + Commons Clause.
// Source, license and IZ2 adaptations: frontend/licenses/particles-sources.txt.
import { Camera, Geometry, Mesh, Program, Renderer } from "ogl";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import { useDecorationActive } from "../motion/useDecorationActive";
import "./Particles.css";

const defaultColors = ["#ffffff", "#c5dcff", "#93b8f2"];
const vertex = /* glsl */ `
  precision highp float;
  attribute vec3 position;
  attribute vec4 random;
  attribute vec3 color;
  uniform mat4 modelMatrix;
  uniform mat4 viewMatrix;
  uniform mat4 projectionMatrix;
  uniform vec2 uBounds;
  uniform float uTime;
  uniform float uDepth;
  uniform float uDistance;
  uniform float uBaseSize;
  uniform float uSizeRandomness;
  uniform float uDpr;
  varying vec4 vRandom;
  varying vec3 vColor;
  void main() {
    vRandom = random;
    vColor = color;
    float z = position.z * uDepth;
    float perspectiveScale = (uDistance - z) / uDistance;
    vec3 pos = vec3(position.xy * uBounds * perspectiveScale, z);
    vec4 mPos = modelMatrix * vec4(pos, 1.0);
    mPos.x += sin(uTime * random.z + 6.28 * random.w) * uBounds.x * 0.018;
    mPos.y += sin(uTime * random.y + 6.28 * random.x) * uBounds.y * 0.018;
    vec4 mvPos = viewMatrix * mPos;
    float variedSize = uBaseSize * (1.0 + uSizeRandomness * (random.x - 0.5));
    gl_PointSize = clamp(variedSize * uDpr / max(-mvPos.z, 1.0), 1.25 * uDpr, 4.0 * uDpr);
    gl_Position = projectionMatrix * mvPos;
  }
`;
const fragment = /* glsl */ `
  precision highp float;
  uniform float uTime;
  uniform float uAlphaParticles;
  varying vec4 vRandom;
  varying vec3 vColor;
  void main() {
    float d = length(gl_PointCoord.xy - vec2(0.5));
    if (d > 0.5) discard;
    float circle = uAlphaParticles > 0.5 ? 1.0 - smoothstep(0.12, 0.5, d) : 1.0;
    float twinkle = 0.84 + 0.16 * sin(uTime * 0.6 + vRandom.y * 6.28);
    float opacity = (0.46 + vRandom.w * 0.26) * twinkle;
    gl_FragColor = vec4(vColor, circle * opacity);
  }
`;

interface ParticlesProps {
  enabled?: boolean;
  particleCount?: number;
  particleColors?: readonly string[];
  particleSpread?: number;
  speed?: number;
  particleBaseSize?: number;
  sizeRandomness?: number;
  cameraDistance?: number;
  alphaParticles?: boolean;
  disableRotation?: boolean;
  moveParticlesOnHover?: boolean;
  particleHoverFactor?: number;
  pixelRatio?: number;
  className?: string;
}

interface ParticlePoint {
  x: number;
  y: number;
  z: number;
  random: number[];
  color: string;
}
interface Runtime {
  start: () => void;
  stop: () => void;
}

const bounded = (value: number, min: number, max: number, fallback: number) =>
  Number.isFinite(value) ? Math.min(Math.max(value, min), max) : fallback;

function createPoints(count: number, palette: string[]): ParticlePoint[] {
  let seed = 160640020;
  const random = () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return seed / 4294967296;
  };
  const columns = Math.ceil(Math.sqrt(count));
  const rows = Math.ceil(count / columns);
  return Array.from({ length: count }, (_, index) => ({
    x: ((((index % columns) + 0.15 + random() * 0.7) / columns) * 2 - 1) * 0.96,
    y:
      (((Math.floor(index / columns) + 0.15 + random() * 0.7) / rows) * 2 - 1) *
      0.96,
    z: random() * 2 - 1,
    random: [random(), random(), random(), random()],
    color: palette[Math.floor(random() * palette.length)],
  }));
}

function hexToRgb(value: string) {
  let hex = value.slice(1);
  if (hex.length === 3) hex = [...hex].map((part) => part + part).join("");
  const integer = Number.parseInt(hex, 16);
  return [
    ((integer >> 16) & 255) / 255,
    ((integer >> 8) & 255) / 255,
    (integer & 255) / 255,
  ];
}

export function Particles({
  enabled = true,
  particleCount = 240,
  particleColors,
  particleSpread = 10,
  speed = 0.14,
  particleBaseSize = 70,
  sizeRandomness = 0.85,
  cameraDistance = 20,
  alphaParticles = true,
  disableRotation = false,
  moveParticlesOnHover = true,
  particleHoverFactor = 0.12,
  pixelRatio = 1.25,
  className = "",
}: ParticlesProps) {
  const count = Math.round(bounded(particleCount, 120, 400, 240));
  const paletteKey =
    (
      particleColors?.filter((color) =>
        /^#[0-9a-f]{3}(?:[0-9a-f]{3})?$/i.test(color),
      ) ?? []
    ).join(",") || defaultColors.join(",");
  const points = useMemo(
    () => createPoints(count, paletteKey.split(",")),
    [count, paletteKey],
  );
  const { ref, active } = useDecorationActive<HTMLDivElement>(enabled);
  const runtime = useRef<Runtime | null>(null);
  const activeRef = useRef(false);
  const [mode, setMode] = useState<"pending" | "webgl" | "fallback">("pending");

  useEffect(() => {
    const container = ref.current;
    if (!container) return;
    const canvas = document.createElement("canvas");
    canvas.setAttribute("aria-hidden", "true");
    const contextOptions: WebGLContextAttributes = {
      alpha: true,
      depth: false,
      stencil: false,
      antialias: false,
      premultipliedAlpha: false,
      preserveDrawingBuffer: false,
      powerPreference: "low-power",
    };
    let renderer: Renderer | undefined;
    let ownedContext: WebGLRenderingContext | WebGL2RenderingContext | null =
      null;
    let geometry: Geometry | undefined;
    let program: Program | undefined;
    let frame: number | null = null;
    let disposed = false;
    let elapsed = 0;
    let previousTime: number | null = null;
    let previousRender: number | null = null;
    const pointer = { x: 0, y: 0 };
    const stop = () => {
      if (frame !== null) cancelAnimationFrame(frame);
      frame = null;
      previousTime = null;
      previousRender = null;
    };
    const pointerMove = (event: PointerEvent) => {
      if (!activeRef.current || event.pointerType === "touch") return;
      pointer.x = (event.clientX / Math.max(window.innerWidth, 1)) * 2 - 1;
      pointer.y = 1 - (event.clientY / Math.max(window.innerHeight, 1)) * 2;
    };
    const pointerLeave = (event: PointerEvent) => {
      if (event.relatedTarget !== null) return;
      pointer.x = 0;
      pointer.y = 0;
    };
    let resize = () => {};
    const dispose = () => {
      if (disposed) return;
      disposed = true;
      stop();
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", pointerMove);
      window.removeEventListener("pointerout", pointerLeave);
      canvas.removeEventListener("webglcontextlost", contextLost);
      runtime.current = null;
      try {
        geometry?.remove();
      } catch {
        /* Context may already be lost. */
      }
      try {
        program?.remove();
      } catch {
        /* Context may already be lost. */
      }
      try {
        (renderer?.gl ?? ownedContext)
          ?.getExtension("WEBGL_lose_context")
          ?.loseContext();
      } catch {
        /* Optional extension. */
      }
      canvas.remove();
    };
    const contextLost = (event: Event) => {
      event.preventDefault();
      dispose();
      setMode("fallback");
    };
    const fail = () => {
      dispose();
      setMode("fallback");
    };

    try {
      const webgl2 = canvas.getContext("webgl2", contextOptions);
      const context = webgl2 || canvas.getContext("webgl", contextOptions);
      ownedContext = context;
      if (!context) {
        fail();
        return dispose;
      }
      const dpr = Math.min(
        bounded(pixelRatio, 0.5, 1.5, 1.25),
        window.devicePixelRatio || 1,
      );
      renderer = new Renderer({
        canvas,
        dpr,
        depth: false,
        alpha: true,
        antialias: false,
        powerPreference: "low-power",
        webgl: webgl2 ? 2 : 1,
      });
      const gl = renderer.gl;
      gl.clearColor(0, 0, 0, 0);
      const distance = bounded(cameraDistance, 12, 40, 20);
      const camera = new Camera(gl, { fov: 42 });
      camera.position.set(0, 0, distance);
      const positions = new Float32Array(count * 3);
      const randoms = new Float32Array(count * 4);
      const colors = new Float32Array(count * 3);
      points.forEach((point, index) => {
        positions.set([point.x, point.y, point.z], index * 3);
        randoms.set(point.random, index * 4);
        colors.set(hexToRgb(point.color), index * 3);
      });
      geometry = new Geometry(gl, {
        position: { size: 3, data: positions },
        random: { size: 4, data: randoms },
        color: { size: 3, data: colors },
      });
      program = new Program(gl, {
        vertex,
        fragment,
        uniforms: {
          uTime: { value: 0 },
          uBounds: { value: [1, 1] },
          uDepth: { value: bounded(particleSpread, 2, 16, 10) * 0.35 },
          uDistance: { value: distance },
          uBaseSize: { value: bounded(particleBaseSize, 24, 90, 70) },
          uSizeRandomness: { value: bounded(sizeRandomness, 0, 1, 0.85) },
          uAlphaParticles: { value: alphaParticles ? 1 : 0 },
          uDpr: { value: dpr },
        },
        transparent: true,
        depthTest: false,
      });
      const particles = new Mesh(gl, { mode: gl.POINTS, geometry, program });
      const draw = () => {
        if (disposed) return;
        renderer!.render({ scene: particles, camera });
      };
      resize = () => {
        if (disposed) return;
        try {
          const width = Math.max(container.clientWidth || window.innerWidth, 1);
          const height = Math.max(
            container.clientHeight || window.innerHeight,
            1,
          );
          renderer!.dpr = Math.min(
            bounded(pixelRatio, 0.5, 1.5, 1.25),
            window.devicePixelRatio || 1,
          );
          renderer!.setSize(width, height);
          camera.perspective({ aspect: width / height });
          const halfHeight = Math.tan((21 * Math.PI) / 180) * distance;
          program!.uniforms.uBounds.value = [
            (halfHeight * width) / height,
            halfHeight,
          ];
          program!.uniforms.uDpr.value = renderer!.dpr;
          if (!document.hidden) draw();
        } catch {
          fail();
        }
      };
      const update = (time: number) => {
        frame = null;
        if (disposed || !activeRef.current) return;
        if (previousRender === null || time - previousRender >= 1000 / 30) {
          const delta =
            previousTime === null ? 0 : Math.min(time - previousTime, 100);
          previousTime = time;
          previousRender = time;
          elapsed += delta * bounded(speed, 0, 0.4, 0.14);
          program!.uniforms.uTime.value = elapsed * 0.001;
          if (moveParticlesOnHover) {
            const hover = bounded(particleHoverFactor, 0, 0.4, 0.12);
            particles.position.x +=
              (-pointer.x * hover - particles.position.x) * 0.04;
            particles.position.y +=
              (-pointer.y * hover - particles.position.y) * 0.04;
          }
          if (!disableRotation) {
            particles.rotation.x = Math.sin(elapsed * 0.0002) * 0.006;
            particles.rotation.y = Math.cos(elapsed * 0.00015) * 0.006;
            particles.rotation.z = Math.sin(elapsed * 0.0001) * 0.012;
          }
          try {
            draw();
          } catch {
            fail();
            return;
          }
        }
        frame = requestAnimationFrame(update);
      };
      runtime.current = {
        start: () => {
          if (!disposed && frame === null)
            frame = requestAnimationFrame(update);
        },
        stop,
      };
      canvas.addEventListener("webglcontextlost", contextLost);
      window.addEventListener("resize", resize, { passive: true });
      if (moveParticlesOnHover) {
        window.addEventListener("pointermove", pointerMove, { passive: true });
        window.addEventListener("pointerout", pointerLeave, { passive: true });
      }
      container.appendChild(canvas);
      resize();
      if (!disposed) {
        setMode("webgl");
        if (activeRef.current) runtime.current?.start();
      }
    } catch {
      fail();
    }
    return dispose;
  }, [
    points,
    count,
    particleSpread,
    speed,
    particleBaseSize,
    sizeRandomness,
    cameraDistance,
    alphaParticles,
    disableRotation,
    moveParticlesOnHover,
    particleHoverFactor,
    pixelRatio,
    ref,
  ]);

  useEffect(() => {
    activeRef.current = active;
    if (active) runtime.current?.start();
    else runtime.current?.stop();
  }, [active, mode]);

  return (
    <div
      className={`iz2-particles ${className}`}
      ref={ref}
      aria-hidden="true"
      data-mode={mode}
      data-active={active}
    >
      <div className="iz2-particles-fallback">
        {points.map((point, index) => (
          <i
            key={index}
            style={
              {
                left: `${(point.x + 1) * 50}%`,
                top: `${(1 - point.y) * 50}%`,
                width: 1.2 + point.random[0] * 1.1,
                height: 1.2 + point.random[0] * 1.1,
                background: point.color,
                opacity: 0.28 + point.random[3] * 0.2,
              } as CSSProperties
            }
          />
        ))}
      </div>
    </div>
  );
}

export default Particles;
