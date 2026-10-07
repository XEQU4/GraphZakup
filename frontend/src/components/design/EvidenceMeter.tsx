import { useId } from "react";
import { formatCount, cx } from "../../lib/utils";
import "./EvidenceMeter.css";

interface EvidenceMeterProps {
  label: string;
  value: number | null;
  total: number | null;
  description?: string;
  className?: string;
}

/** Coverage of saved records only; never substitutes for confidence or risk. */
export function EvidenceMeter({
  label,
  value,
  total,
  description,
  className,
}: EvidenceMeterProps) {
  const id = useId();
  const valid =
    value !== null &&
    total !== null &&
    Number.isSafeInteger(value) &&
    Number.isSafeInteger(total) &&
    value >= 0 &&
    total >= value;
  const fraction = valid && total > 0 ? value / total : 0;
  const countText = valid
    ? `${formatCount(value)} of ${formatCount(total)} records`
    : "Saved counts are unavailable";

  return (
    <div className={cx("iz2-evidence-meter", className)}>
      <div className="iz2-evidence-meter-heading">
        <span id={id + "-label"}>{label}</span>
        <span className="iz2-evidence-meter-count">
          {valid ? (
            <>
              <strong>{formatCount(value)}</strong>
              <span aria-hidden="true">/</span>
              <span>{formatCount(total)}</span>
            </>
          ) : (
            "Not available"
          )}
        </span>
      </div>
      <div
        className="iz2-evidence-meter-track"
        role={valid && total > 0 ? "meter" : undefined}
        aria-labelledby={valid && total > 0 ? id + "-label" : undefined}
        aria-describedby={description ? id + "-description" : undefined}
        aria-valuemin={valid && total > 0 ? 0 : undefined}
        aria-valuemax={valid && total > 0 ? total : undefined}
        aria-valuenow={valid && total > 0 ? value : undefined}
        aria-valuetext={valid && total > 0 ? countText : undefined}
        aria-hidden={!valid || total === 0 ? true : undefined}
      >
        <span
          className="iz2-evidence-meter-fill"
          style={{ width: fraction * 100 + "%" }}
        />
      </div>
      {valid && total === 0 ? (
        <p className="iz2-evidence-meter-empty">No saved records to assess</p>
      ) : null}
      {description ? (
        <p id={id + "-description"} className="iz2-evidence-meter-description">
          {description}
        </p>
      ) : null}
    </div>
  );
}
