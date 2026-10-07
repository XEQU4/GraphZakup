import { useDecorationActive } from "./useDecorationActive";
import "./SectionEmblem.css";

type SectionKind = "companies" | "people" | "contracts";

function CompanyMark() {
  return (
    <>
      <g className="section-emblem-cube">
        <path
          className="section-emblem-face-top"
          d="m60 28 27 16-27 16-27-16Z"
        />
        <path className="section-emblem-face-left" d="M33 44v33l27 16V60Z" />
        <path className="section-emblem-face-right" d="M87 44v33L60 93V60Z" />
        <path
          className="section-emblem-outline"
          d="m60 28 27 16v33L60 93 33 77V44Zm0 32v33M33 44l27 16 27-16"
        />
        <path
          className="section-emblem-sweep"
          pathLength="1"
          d="m60 28 27 16v33L60 93 33 77V44Z"
        />
      </g>
      <path
        className="section-emblem-guide"
        d="M19 61h7m68 0h7M60 15v6m0 78v6"
      />
    </>
  );
}

function PersonMark() {
  return (
    <>
      <circle className="section-emblem-person-halo" cx="60" cy="60" r="41" />
      <g className="section-emblem-person-orbit">
        <circle
          className="section-emblem-orbit-arc"
          cx="60"
          cy="60"
          r="41"
          pathLength="1"
        />
        <circle className="section-emblem-orbit-point" cx="60" cy="19" r="3" />
      </g>
      <circle className="section-emblem-person-head" cx="60" cy="46" r="12" />
      <path
        className="section-emblem-person-body"
        d="M37 87v-4c0-12 9-21 23-21s23 9 23 21v4"
      />
      <path className="section-emblem-scan" d="M32 59h56" />
      <path
        className="section-emblem-guide"
        d="M15 39v-9h9m81 9v-9h-9M15 81v9h9m81-9v9h-9"
      />
    </>
  );
}

function ContractMark() {
  return (
    <>
      <path className="section-emblem-paper" d="M38 25h29l17 17v53H38Z" />
      <path className="section-emblem-outline" d="M67 25v17h17" />
      <path
        className="section-emblem-document-base"
        d="M49 55h24M49 65h24M49 75h18M49 85h12"
      />
      {[55, 65, 75, 85].map((y, index) => (
        <path
          className={
            "section-emblem-document-line section-emblem-line-" + index
          }
          pathLength="1"
          d={`M49 ${y}h${24 - Math.max(index - 1, 0) * 6}`}
          key={y}
        />
      ))}
      <path className="section-emblem-guide" d="M25 40v45m70-35v35" />
      <circle className="section-emblem-registration" cx="25" cy="32" r="2" />
      <circle className="section-emblem-registration" cx="95" cy="92" r="2" />
    </>
  );
}

/** Original decorative SVG artwork; no data, state or verification claim. */
export default function SectionEmblem({ kind }: { kind: SectionKind }) {
  const { ref, active } = useDecorationActive<HTMLDivElement>();
  return (
    <div
      className={"section-emblem section-emblem-" + kind}
      aria-hidden="true"
      data-active={active ? "true" : "false"}
      ref={ref}
    >
      <span className="section-emblem-edge" />
      <svg viewBox="0 0 120 120" fill="none" focusable="false">
        {kind === "companies" ? <CompanyMark /> : null}
        {kind === "people" ? <PersonMark /> : null}
        {kind === "contracts" ? <ContractMark /> : null}
      </svg>
    </div>
  );
}
