// React Bits Border Glow edge/conic technique, adapted for native IZ2 elements.
// Copyright (c) 2026 David Haz. MIT + Commons Clause; see licenses/react-bits.txt.
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type FocusEvent,
  type HTMLAttributes,
  type PointerEvent,
  type RefObject,
} from "react";
import { useDecorationActive } from "../motion/useDecorationActive";
import "./BorderGlow.css";

const DEFAULT_COLORS = ["#78aaff", "#daeaff", "#3e6ee8"] as const;
const GRADIENT_POSITIONS = [
  "80% 55%",
  "69% 34%",
  "8% 6%",
  "41% 38%",
  "86% 85%",
  "82% 18%",
  "51% 4%",
];
const COLOR_MAP = [0, 1, 2, 0, 1, 2, 1];

export interface BorderGlowOptions {
  enabled?: boolean;
  edgeSensitivity?: number;
  glowRadius?: number;
  glowIntensity?: number;
  coneSpread?: number;
  fillOpacity?: number;
  borderRadius?: number;
  glowColor?: string;
  colors?: readonly [string, string, string];
}

function glowStyle({
  edgeSensitivity = 30,
  glowRadius = 28,
  glowIntensity = 1,
  coneSpread = 25,
  fillOpacity = 0.16,
  borderRadius,
  glowColor = "214 90 84",
  colors = DEFAULT_COLORS,
}: BorderGlowOptions): CSSProperties {
  const match = glowColor.match(/([\d.]+)\s+([\d.]+)%?\s+([\d.]+)%?/);
  const [h, s, l] = match ? match.slice(1, 4).map(Number) : [214, 90, 84];
  const intensity = Math.max(0, Math.min(glowIntensity, 2));
  const variables: Record<string, string | number> = {
    "--border-glow-sensitivity": Math.max(0, Math.min(edgeSensitivity, 75)),
    "--border-glow-padding": `${Math.max(0, Math.min(glowRadius, 60))}px`,
    "--border-glow-cone": Math.max(5, Math.min(coneSpread, 35)),
    "--border-glow-fill": Math.max(0, Math.min(fillOpacity, 0.4)),
    "--border-glow-edge": 0,
    "--border-glow-angle": "45deg",
    "--border-glow-base": `linear-gradient(${colors[0]} 0 100%)`,
  };
  if (borderRadius !== undefined)
    variables.borderRadius = `${Math.max(0, borderRadius)}px`;
  [100, 60, 50, 40, 30, 20, 10].forEach((opacity) => {
    variables[`--border-glow-color-${opacity}`] =
      `hsl(${h}deg ${s}% ${l}% / ${Math.min(opacity * intensity, 100)}%)`;
  });
  GRADIENT_POSITIONS.forEach((position, index) => {
    variables[`--border-glow-gradient-${index + 1}`] =
      `radial-gradient(at ${position}, ${colors[COLOR_MAP[index]]} 0px, transparent 50%)`;
  });
  return variables as CSSProperties;
}

/** Spread these props on the original link/section; no navigation is intercepted. */
export function useBorderGlow<T extends HTMLElement = HTMLDivElement>(
  options: BorderGlowOptions = {},
) {
  const { ref, active } = useDecorationActive<T>(options.enabled ?? true);
  const [focused, setFocused] = useState(false);
  const frame = useRef<number | null>(null);
  const pending = useRef<{
    element: T;
    x: number;
    y: number;
    width: number;
    height: number;
  } | null>(null);

  const cancel = useCallback(() => {
    if (frame.current !== null) cancelAnimationFrame(frame.current);
    frame.current = null;
    pending.current = null;
  }, []);

  const reset = useCallback(() => {
    cancel();
    const target = ref.current;
    if (!target) return;
    target.dataset.borderGlowHover = "false";
    target.style.setProperty("--border-glow-edge", "0");
    target.style.setProperty("--border-glow-angle", "45deg");
  }, [cancel, ref]);

  useEffect(() => {
    if (!active) {
      reset();
      setFocused(false);
    }
    return reset;
  }, [active, reset]);

  const move = (event: PointerEvent<T>) => {
    if (!active || event.pointerType === "touch") return;
    const target = event.currentTarget;
    const box = target.getBoundingClientRect();
    if (!box.width || !box.height) return;
    target.dataset.borderGlowHover = "true";
    pending.current = {
      element: target,
      x: Math.min(Math.max(event.clientX - box.left, 0), box.width),
      y: Math.min(Math.max(event.clientY - box.top, 0), box.height),
      width: box.width,
      height: box.height,
    };
    if (frame.current !== null) return;
    frame.current = requestAnimationFrame(() => {
      frame.current = null;
      const next = pending.current;
      pending.current = null;
      if (!next?.element.isConnected || document.hidden) return;
      const cx = next.width / 2;
      const cy = next.height / 2;
      const dx = next.x - cx;
      const dy = next.y - cy;
      const edge = Math.min(Math.max(Math.abs(dx) / cx, Math.abs(dy) / cy), 1);
      const degrees = ((Math.atan2(dy, dx) * 180) / Math.PI + 450) % 360;
      next.element.style.setProperty(
        "--border-glow-edge",
        (edge * 100).toFixed(3),
      );
      next.element.style.setProperty(
        "--border-glow-angle",
        `${degrees.toFixed(3)}deg`,
      );
    });
  };

  const blur = (event: FocusEvent<T>) => {
    if (
      !(event.relatedTarget instanceof Node) ||
      !event.currentTarget.contains(event.relatedTarget)
    ) {
      setFocused(false);
      reset();
    }
  };

  const decoration = (
    <span className="iz2-border-glow__decoration" aria-hidden="true">
      <span className="iz2-border-glow__border">
        <span className="iz2-border-glow__mesh" />
      </span>
      <span className="iz2-border-glow__fill" />
      <span className="iz2-border-glow__edge" />
    </span>
  );

  return {
    active,
    decoration,
    surfaceProps: {
      ref,
      className: "iz2-border-glow",
      style: glowStyle(options),
      "data-border-glow-active": active,
      "data-border-glow-hover": false,
      "data-border-glow-focus": focused,
      onPointerEnter: move,
      onPointerMove: move,
      onPointerLeave: reset,
      onPointerCancel: reset,
      onFocusCapture: () => {
        if (active) setFocused(true);
      },
      onBlurCapture: blur,
    } as const,
  };
}

export interface BorderGlowProps
  extends HTMLAttributes<HTMLElement>, BorderGlowOptions {
  as?: "div" | "section" | "article";
}

/** Non-interactive container; children keep their original roles and tab order. */
export function BorderGlow({
  as: Tag = "div",
  children,
  className = "",
  style,
  enabled,
  edgeSensitivity,
  glowRadius,
  glowIntensity,
  coneSpread,
  fillOpacity,
  borderRadius,
  glowColor,
  colors,
  onPointerEnter,
  onPointerMove,
  onPointerLeave,
  onPointerCancel,
  onFocusCapture,
  onBlurCapture,
  ...props
}: BorderGlowProps) {
  const { surfaceProps, decoration } = useBorderGlow<HTMLDivElement>({
    enabled,
    edgeSensitivity,
    glowRadius,
    glowIntensity,
    coneSpread,
    fillOpacity,
    borderRadius,
    glowColor,
    colors,
  });
  return (
    <Tag
      {...props}
      {...surfaceProps}
      ref={surfaceProps.ref as RefObject<HTMLDivElement>}
      className={`${surfaceProps.className} ${className}`}
      style={{ ...surfaceProps.style, ...style }}
      onPointerEnter={(event) => {
        onPointerEnter?.(event);
        if (!event.defaultPrevented) surfaceProps.onPointerEnter(event);
      }}
      onPointerMove={(event) => {
        onPointerMove?.(event);
        if (!event.defaultPrevented) surfaceProps.onPointerMove(event);
      }}
      onPointerLeave={(event) => {
        onPointerLeave?.(event);
        surfaceProps.onPointerLeave();
      }}
      onPointerCancel={(event) => {
        onPointerCancel?.(event);
        surfaceProps.onPointerCancel();
      }}
      onFocusCapture={(event) => {
        onFocusCapture?.(event);
        if (!event.defaultPrevented) surfaceProps.onFocusCapture();
      }}
      onBlurCapture={(event) => {
        onBlurCapture?.(event);
        surfaceProps.onBlurCapture(event);
      }}
    >
      {decoration}
      {children}
    </Tag>
  );
}
