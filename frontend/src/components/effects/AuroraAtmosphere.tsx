// Gradient technique adapted from Lightswind UI's Aurora Background.
// Copyright (c) 2025 Muhilan (codewithMUHILAN). MIT; see licenses/lightswind.txt.
import { useEffect, useRef } from "react";
import type { CSSProperties } from "react";

import "./AuroraAtmosphere.css";

interface AuroraAtmosphereProps {
  enabled?: boolean;
  className?: string;
}

const points = [
  [55, 19, 0],
  [71, 11, 3],
  [92, 31, 6],
  [44, 46, 1],
  [79, 57, 4],
  [63, 78, 8],
  [86, 82, 2],
  [95, 64, 7],
  [51, 69, 5],
  [33, 22, 9],
] as const;

/** Decorative light only; it carries no evidence or generated data. */
export function AuroraAtmosphere({
  enabled = true,
  className = "",
}: AuroraAtmosphereProps) {
  const element = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const target = element.current;
    if (!target) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    let visible = false;
    const update = () => {
      target.dataset.active = String(
        enabled && visible && !document.hidden && !reduced.matches,
      );
    };
    const observer =
      typeof IntersectionObserver === "undefined"
        ? null
        : new IntersectionObserver(
            ([entry]) => {
              visible = entry.isIntersecting;
              update();
            },
            { threshold: 0 },
          );
    if (observer) observer.observe(target);
    else visible = true;
    update();
    reduced.addEventListener("change", update);
    document.addEventListener("visibilitychange", update);
    return () => {
      observer?.disconnect();
      reduced.removeEventListener("change", update);
      document.removeEventListener("visibilitychange", update);
      target.dataset.active = "false";
    };
  }, [enabled]);

  return (
    <div
      ref={element}
      className={`aurora-atmosphere ${className}`}
      data-active="false"
      aria-hidden="true"
    >
      <div className="aurora-atmosphere__wash" />
      <div className="aurora-atmosphere__veil aurora-atmosphere__veil--far" />
      <div className="aurora-atmosphere__veil aurora-atmosphere__veil--near" />
      <div className="aurora-atmosphere__dust">
        {points.map(([x, y, delay], index) => (
          <i
            key={index}
            style={
              {
                left: `${x}%`,
                top: `${y}%`,
                "--dust-delay": `${-delay}s`,
                "--dust-duration": `${13 + index}s`,
              } as CSSProperties
            }
          />
        ))}
      </div>
    </div>
  );
}
