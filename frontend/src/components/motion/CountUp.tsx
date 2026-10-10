// Adapted from React Bits CountUp (David Haz); see licenses/react-bits.txt.
// https://reactbits.dev/text-animations/count-up
import { useEffect, useLayoutEffect, useRef } from "react";
import { useMotionValue } from "motion/react";
import { formatCount } from "../../lib/utils";
import { useI18n } from "../../i18n";
import { useMotionPreferences } from "../MotionPreferences";
import { useDecorationActive } from "./useDecorationActive";

interface CountUpProps {
  /** Saved non-negative integer counts only; never money, identifiers or risk. */
  value: number | null | undefined;
  className?: string;
  /** Seconds; animation is capped at three seconds. */
  duration?: number;
}

interface CountAnimation {
  from: number;
  target: number;
  elapsed: number;
}

export default function CountUp({
  value,
  className,
  duration = 1.1,
}: CountUpProps) {
  const { language } = useI18n();
  const target =
    typeof value === "number" && Number.isSafeInteger(value) && value >= 0
      ? value
      : null;
  const finalText = target === null ? "—" : formatCount(target);
  const widestLabel = useRef(finalText);
  if (finalText.length > widestLabel.current.length)
    widestLabel.current = finalText;
  const milliseconds = Number.isFinite(duration)
    ? Math.min(Math.max(duration, 0), 3) * 1000
    : 1100;
  const { enabled } = useMotionPreferences();
  const { ref, active } = useDecorationActive<HTMLSpanElement>();
  const visual = useRef<HTMLSpanElement>(null);
  const previousTarget = useRef<number | null | undefined>(undefined);
  const animation = useRef<CountAnimation | null>(null);
  const frame = useRef<number | null>(null);
  const motionValue = useMotionValue(enabled ? 0 : (target ?? 0));

  const cancelFrame = () => {
    if (frame.current !== null) cancelAnimationFrame(frame.current);
    frame.current = null;
  };

  useLayoutEffect(() => {
    return motionValue.on("change", (latest: number) => {
      if (visual.current && target !== null) {
        visual.current.textContent = formatCount(Math.round(latest));
      }
    });
  }, [motionValue, target]);

  useLayoutEffect(() => {
    const changed = previousTarget.current !== target;
    if (changed) {
      cancelFrame();
      const from =
        typeof previousTarget.current === "number" ? motionValue.get() : 0;
      animation.current =
        target !== null && enabled && milliseconds > 0 && from !== target
          ? { from, target, elapsed: 0 }
          : null;
      motionValue.set(animation.current ? from : (target ?? 0));
      previousTarget.current = target;
    }
    if (!enabled || milliseconds === 0) {
      cancelFrame();
      animation.current = null;
      motionValue.set(target ?? 0);
    }
    if (visual.current) {
      visual.current.textContent =
        target === null ? "—" : formatCount(Math.round(motionValue.get()));
    }
  }, [target, enabled, milliseconds, motionValue, language]);

  useEffect(() => {
    const run = animation.current;
    if (!active || !enabled || !run || milliseconds === 0) return;
    let previousTime: number | null = null;
    let disposed = false;
    const tick = (time: number) => {
      frame.current = null;
      if (disposed || animation.current !== run) return;
      if (previousTime !== null) {
        run.elapsed += Math.max(0, time - previousTime);
      }
      previousTime = time;
      const progress = Math.min(run.elapsed / milliseconds, 1);
      const eased = 1 - (1 - progress) ** 3;
      const next = Math.round(run.from + (run.target - run.from) * eased);
      motionValue.set(
        Math.min(
          Math.max(next, Math.min(run.from, run.target)),
          Math.max(run.from, run.target),
        ),
      );
      if (progress >= 1) {
        motionValue.set(run.target);
        animation.current = null;
      } else {
        frame.current = requestAnimationFrame(tick);
      }
    };
    frame.current = requestAnimationFrame(tick);
    return () => {
      disposed = true;
      cancelFrame();
    };
  }, [active, enabled, milliseconds, target, motionValue]);

  return (
    <span
      className={className}
      ref={ref}
      style={{ display: "inline-grid", fontVariantNumeric: "tabular-nums" }}
    >
      <span
        aria-hidden="true"
        style={{ gridArea: "1 / 1", visibility: "hidden" }}
      >
        {widestLabel.current}
      </span>
      <span
        ref={visual}
        aria-hidden="true"
        data-countup-visual=""
        style={{ gridArea: "1 / 1" }}
      >
        {!enabled || target === null
          ? finalText
          : formatCount(Math.round(motionValue.get()))}
      </span>
      <span className="sr-only">{finalText}</span>
    </span>
  );
}
