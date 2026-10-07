// Interaction inspired by React Bits Tech Text supplied by the user.
// HTML glyphs preserve heading semantics, selection and responsive wrapping.
// Source/license: frontend/licenses/text-motion-sources.txt.
import { useEffect, useState, type CSSProperties, type RefObject } from "react";
import { useMotionPreferences } from "../MotionPreferences";
import { useDecorationActive } from "./useDecorationActive";
import "./TechHeading.css";

interface TechHeadingProps {
  text: string | string[];
  as?: "h1" | "h2" | "h3" | "span";
  id?: string;
  className?: string;
  enabled?: boolean;
  accentLine?: number;
}

interface GlyphSelection {
  index: number;
  label: string;
  width: number;
  height: number;
  baseline: number;
  labelLeft: number;
}

export function TechHeading({
  text,
  as: Tag = "h2",
  id,
  className = "",
  enabled = true,
  accentLine,
}: TechHeadingProps) {
  const lines = Array.isArray(text) ? text : [text];
  const { enabled: allowed } = useMotionPreferences();
  const canAnimate = enabled && allowed;
  const { ref, active } = useDecorationActive<HTMLHeadingElement>(enabled);
  const [revealed, setRevealed] = useState(!canAnimate);
  const [selected, setSelected] = useState<GlyphSelection | null>(null);
  useEffect(() => {
    if (!canAnimate) setRevealed(true);
    if (!active) setSelected(null);
  }, [canAnimate, active]);
  const totalGlyphs = Array.from(lines.join("")).filter(
    (character) => !/\s/.test(character),
  ).length;
  // Hover can cancel the final glyph animation, so completion also has a bounded fallback.
  useEffect(() => {
    if (!active || !canAnimate || revealed) return;
    const completion = window.setTimeout(
      () => setRevealed(true),
      Math.min(Math.max(totalGlyphs - 1, 0) * 23, 1150) + 620,
    );
    return () => window.clearTimeout(completion);
  }, [active, canAnimate, revealed, totalGlyphs]);
  const accent = accentLine ?? (lines.length > 1 ? lines.length - 1 : -1);
  let index = 0;

  return (
    <Tag
      ref={ref as RefObject<HTMLHeadingElement & HTMLSpanElement>}
      id={id}
      aria-label={lines.join(" ")}
      className={`tech-heading ${className}`}
      data-active={active}
      data-enabled={canAnimate}
      data-revealed={revealed}
      onPointerLeave={() => setSelected(null)}
      onPointerCancel={() => setSelected(null)}
    >
      {lines.map((line, lineIndex) => (
        <span
          key={lineIndex}
          aria-hidden="true"
          className={`tech-heading__line ${lineIndex === accent ? "tech-heading__line--accent" : ""}`}
        >
          {line.split(/(\s+)/).map((word, wordIndex) =>
            /^\s+$/.test(word) ? (
              word
            ) : (
              <span className="tech-heading__word" key={wordIndex}>
                {Array.from(word).map((character) => {
                  const glyph = index++;
                  const selection =
                    active && selected?.index === glyph ? selected : null;
                  return (
                    <span
                      key={glyph}
                      className="tech-heading__glyph"
                      data-selected={Boolean(selection)}
                      style={
                        {
                          "--tech-delay": `${Math.min(glyph * 23, 1150)}ms`,
                          "--tech-scan-delay": `${glyph * 30}ms`,
                        } as CSSProperties
                      }
                      onPointerEnter={(event) => {
                        if (!active || event.pointerType === "touch") return;
                        const box = event.currentTarget.getBoundingClientRect();
                        const heading = event.currentTarget
                          .closest(".tech-heading")!
                          .getBoundingClientRect();
                        const label = `${character} / ${Math.round(box.width)} × ${Math.round(box.height)}`;
                        const labelWidth = label.length * 5 + 12;
                        const baseline =
                          event.currentTarget
                            .querySelector(".tech-heading__baseline")
                            ?.getBoundingClientRect().top ?? box.bottom;
                        setSelected({
                          index: glyph,
                          label,
                          width: box.width,
                          height: box.height,
                          baseline: baseline - box.top,
                          labelLeft: Math.max(
                            heading.left - box.left,
                            Math.min(-3, heading.right - box.left - labelWidth),
                          ),
                        });
                      }}
                      onPointerLeave={() =>
                        setSelected((previous) =>
                          previous?.index === glyph ? null : previous,
                        )
                      }
                      onAnimationEnd={(event) => {
                        if (
                          event.animationName === "iz2-tech-reveal" &&
                          glyph === totalGlyphs - 1
                        )
                          setRevealed(true);
                      }}
                    >
                      {character}
                      <span
                        className="tech-heading__baseline"
                        aria-hidden="true"
                      />
                      {selection && (
                        <>
                          <svg
                            className="tech-heading__outline"
                            width={selection.width}
                            height={selection.height}
                            viewBox={`0 0 ${selection.width} ${selection.height}`}
                            aria-hidden="true"
                            focusable="false"
                          >
                            <text x="0" y={selection.baseline}>
                              {character}
                            </text>
                          </svg>
                          <span
                            className="tech-heading__measure"
                            style={{ left: selection.labelLeft }}
                            aria-hidden="true"
                          >
                            {selection.label}
                          </span>
                        </>
                      )}
                    </span>
                  );
                })}
              </span>
            ),
          )}
        </span>
      ))}
    </Tag>
  );
}
