import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FocusEvent,
  type HTMLAttributes,
  type PointerEvent,
} from "react";
import { useMotionPreferences } from "../MotionPreferences";
import { cx } from "../../lib/utils";
import "./SpotlightSurface.css";

/** Decorative interaction only: keep the element's original link/button semantics. */
export function useSpotlight<T extends HTMLElement = HTMLDivElement>({
  disabled = false,
}: { disabled?: boolean } = {}) {
  const { enabled } = useMotionPreferences();
  const followsPointer = enabled && !disabled;
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const frame = useRef<number | null>(null);
  const pending = useRef<{ element: T; x: number; y: number } | null>(null);

  const cancel = useCallback(() => {
    if (frame.current !== null) cancelAnimationFrame(frame.current);
    frame.current = null;
    pending.current = null;
  }, []);

  useEffect(() => {
    if (!followsPointer) cancel();
    return cancel;
  }, [cancel, followsPointer]);

  const move = (event: PointerEvent<T>) => {
    if (!followsPointer || event.pointerType === "touch") return;
    const element = event.currentTarget;
    const bounds = element.getBoundingClientRect();
    pending.current = {
      element,
      x: Math.min(Math.max(event.clientX - bounds.left, 0), bounds.width),
      y: Math.min(Math.max(event.clientY - bounds.top, 0), bounds.height),
    };
    if (frame.current !== null) return;
    frame.current = requestAnimationFrame(() => {
      frame.current = null;
      const next = pending.current;
      pending.current = null;
      if (!next?.element.isConnected) return;
      next.element.style.setProperty("--spotlight-x", `${next.x}px`);
      next.element.style.setProperty("--spotlight-y", `${next.y}px`);
    });
  };

  const leave = () => {
    setHovered(false);
    cancel();
  };

  const blur = (event: FocusEvent<T>) => {
    if (
      !event.relatedTarget ||
      !(event.relatedTarget instanceof Node) ||
      !event.currentTarget.contains(event.relatedTarget)
    ) {
      setFocused(false);
    }
  };

  return {
    active: hovered || focused,
    surfaceProps: {
      className: "iz2-spotlight",
      "data-spotlight-motion": followsPointer ? "on" : "off",
      onPointerEnter: (event: PointerEvent<T>) => {
        if (event.pointerType !== "touch") setHovered(true);
      },
      onPointerMove: move,
      onPointerLeave: leave,
      onPointerCancel: leave,
      onFocusCapture: () => setFocused(true),
      onBlurCapture: blur,
    } as const,
  };
}

export interface SpotlightSurfaceProps extends HTMLAttributes<HTMLDivElement> {
  disabled?: boolean;
}

/** Wrap arbitrary saved content; this surface adds no tab stop or click action. */
export function SpotlightSurface({
  children,
  className,
  disabled,
  onPointerEnter,
  onPointerMove,
  onPointerLeave,
  onPointerCancel,
  onFocusCapture,
  onBlurCapture,
  ...props
}: SpotlightSurfaceProps) {
  const { surfaceProps } = useSpotlight<HTMLDivElement>({ disabled });
  return (
    <div
      {...props}
      {...surfaceProps}
      className={cx(surfaceProps.className, className)}
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
        surfaceProps.onFocusCapture();
      }}
      onBlurCapture={(event) => {
        onBlurCapture?.(event);
        surfaceProps.onBlurCapture(event);
      }}
    >
      {children}
    </div>
  );
}
