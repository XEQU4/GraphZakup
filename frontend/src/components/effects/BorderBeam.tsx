// Adapted from Magic UI Border Beam, Copyright (c) Magic UI, MIT.
// Full notice: frontend/licenses/magic-ui.txt. Styling and motion gates customised for IZ2.
import { useRef } from "react";
import {
  motion,
  useReducedMotion,
  useInView,
  type MotionStyle,
} from "motion/react";
export function BorderBeam({
  enabled = true,
  duration = 18,
  size = 140,
}: {
  enabled?: boolean;
  duration?: number;
  size?: number;
}) {
  const reduced = useReducedMotion();
  const frame = useRef<HTMLDivElement>(null);
  const visible = useInView(frame);
  return (
    <div ref={frame} className="border-beam-frame" aria-hidden="true">
      {enabled && !reduced && visible && (
        <motion.div
          className="border-beam-light"
          style={
            {
              width: size,
              offsetPath: "rect(0 auto auto 0 round 20px)",
            } as MotionStyle
          }
          initial={{ offsetDistance: "0%" }}
          animate={{ offsetDistance: ["0%", "100%"] }}
          transition={{ repeat: Infinity, ease: "linear", duration }}
        />
      )}
    </div>
  );
}
