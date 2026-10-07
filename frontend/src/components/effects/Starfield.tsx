import type { CSSProperties } from "react";
import { useMotionPreferences } from "../MotionPreferences";
import { useDecorationActive } from "../motion/useDecorationActive";
import "./Starfield.css";

// Stable decorative coordinates; independent of application data and renders.
let seed = 312052602;
const random = () => {
  seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
  return seed / 4294967296;
};
const stars = Array.from({ length: 66 }, (_, index) => ({
  left: (((index % 11) + 0.14 + random() * 0.72) / 11) * 100,
  top: ((Math.floor(index / 11) + 0.12 + random() * 0.76) / 6) * 100,
  size: 0.75 + random() * 0.8,
  opacity: 0.23 + random() * 0.28,
  duration: 6.5 + random() * 8.5,
  delay: -random() * 15,
}));

/** A low-contrast decorative background; place application surfaces above it. */
export function Starfield() {
  const { enabled } = useMotionPreferences();
  const { ref, active } = useDecorationActive<HTMLDivElement>();
  return (
    <div
      className="iz2-starfield"
      ref={ref}
      aria-hidden="true"
      data-active={active ? "true" : "false"}
      data-enabled={enabled ? "true" : "false"}
    >
      {stars.map((star, index) => (
        <span
          className="iz2-starfield-star"
          key={index}
          style={
            {
              left: `${star.left}%`,
              top: `${star.top}%`,
              width: star.size,
              height: star.size,
              "--star-opacity": star.opacity,
              "--star-duration": `${star.duration}s`,
              "--star-delay": `${star.delay}s`,
            } as CSSProperties
          }
        />
      ))}
    </div>
  );
}

export default Starfield;
