import type { CSSProperties } from "react";
import { useMotionPreferences } from "../MotionPreferences";
import { useDecorationActive } from "./useDecorationActive";
import "./GroupGlyph.css";

interface GroupGlyphProps {
  className?: string;
  size?: number;
}

/** Original constellation artwork; use beside the real saved-group count. */
export function GroupGlyph({ className = "", size }: GroupGlyphProps) {
  const { ref, active } = useDecorationActive<HTMLSpanElement>();
  const { enabled } = useMotionPreferences();
  const style =
    size !== undefined && Number.isFinite(size)
      ? ({
          "--group-glyph-size": `${Math.max(12, Math.min(size, 64))}px`,
        } as CSSProperties)
      : undefined;
  return (
    <span
      className={`iz2-group-glyph ${className}`}
      aria-hidden="true"
      ref={ref}
      style={style}
      data-active={active ? "true" : "false"}
      data-enabled={enabled ? "true" : "false"}
    >
      <svg viewBox="0 0 28 28" fill="none" focusable="false">
        <g className="iz2-group-glyph-network">
          <path
            className="iz2-group-glyph-links"
            d="m6 8 8 6 7-9M14 14l10 6M14 14 8 24M6 8l2 16m13-19 3 15"
          />
          <path
            className="iz2-group-glyph-flow"
            pathLength="1"
            d="m6 8 8 6 7-9M14 14l10 6M14 14 8 24"
          />
          <circle className="iz2-group-glyph-node" cx="6" cy="8" r="2" />
          <circle className="iz2-group-glyph-node" cx="21" cy="5" r="2" />
          <circle className="iz2-group-glyph-node" cx="24" cy="20" r="2" />
          <circle className="iz2-group-glyph-node" cx="8" cy="24" r="2" />
        </g>
        <circle className="iz2-group-glyph-pulse" cx="14" cy="14" r="4" />
        <circle className="iz2-group-glyph-core" cx="14" cy="14" r="2.5" />
      </svg>
    </span>
  );
}

export default GroupGlyph;
