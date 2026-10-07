import { useEffect, useId, useRef, useState } from "react";
import { useInView } from "motion/react";
import { CubeIcon, FileTextIcon, PersonIcon } from "@radix-ui/react-icons";

/** Decorative illustration of the workspace's three record types, not a graph. */
export function EvidenceSculpture({ enabled }: { enabled: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const visible = useInView(ref);
  const [pageVisible, setPageVisible] = useState(!document.hidden);
  const id = useId().replace(/:/g, "");
  useEffect(() => {
    const update = () => setPageVisible(!document.hidden);
    document.addEventListener("visibilitychange", update);
    return () => document.removeEventListener("visibilitychange", update);
  }, []);
  return (
    <div
      ref={ref}
      className="evidence-sculpture"
      data-active={enabled && visible && pageVisible}
      aria-hidden="true"
    >
      <div className="sculpture-ground" />
      <svg className="sculpture-art" viewBox="0 0 560 430" fill="none">
        <defs>
          <linearGradient
            id={id + "-top"}
            x1="170"
            y1="140"
            x2="377"
            y2="270"
            gradientUnits="userSpaceOnUse"
          >
            <stop stopColor="#bbefff" stopOpacity=".9" />
            <stop offset=".42" stopColor="#4184ff" stopOpacity=".7" />
            <stop offset="1" stopColor="#2c35c7" stopOpacity=".85" />
          </linearGradient>
          <linearGradient
            id={id + "-left"}
            x1="155"
            y1="180"
            x2="285"
            y2="325"
            gradientUnits="userSpaceOnUse"
          >
            <stop stopColor="#137ff6" stopOpacity=".85" />
            <stop offset="1" stopColor="#101b4f" stopOpacity=".98" />
          </linearGradient>
          <linearGradient
            id={id + "-right"}
            x1="285"
            y1="224"
            x2="400"
            y2="265"
            gradientUnits="userSpaceOnUse"
          >
            <stop stopColor="#2f47d8" stopOpacity=".92" />
            <stop offset="1" stopColor="#15164c" stopOpacity=".96" />
          </linearGradient>
          <linearGradient
            id={id + "-edge"}
            x1="170"
            y1="130"
            x2="400"
            y2="300"
            gradientUnits="userSpaceOnUse"
          >
            <stop stopColor="#c8f5ff" />
            <stop offset=".5" stopColor="#60d4ff" />
            <stop offset="1" stopColor="#7a7bff" />
          </linearGradient>
          <filter
            id={id + "-glow"}
            x="-50%"
            y="-50%"
            width="200%"
            height="200%"
          >
            <feGaussianBlur stdDeviation="4" />
          </filter>
        </defs>
        <g
          className="sculpture-connectors"
          stroke="#4b9be8"
          strokeOpacity=".55"
          strokeWidth="1.2"
        >
          <path d="M85 135L182 181M383 166L475 98M287 287L429 339" />
          <circle cx="85" cy="135" r="4" fill="#a8e6ff" />
          <circle cx="475" cy="98" r="4" fill="#b2c4ff" />
          <circle cx="429" cy="339" r="4" fill="#9dccff" />
        </g>
        <g className="sculpture-platform">
          <path
            d="M149 274L280 201L411 274L280 347Z"
            fill="#0c214e"
            stroke="#3873bd"
            strokeOpacity=".5"
          />
          <path
            d="M149 274V286L280 359L411 286V274L280 347Z"
            fill="#0a1631"
            stroke="#275290"
            strokeOpacity=".6"
          />
        </g>
        <g className="sculpture-prism">
          {[52, 26, 0].map((offset, index) => (
            <g
              key={offset}
              transform={"translate(0 " + offset + ")"}
              opacity={index === 0 ? 0.6 : 1}
            >
              <path
                d="M162 162L280 96L398 162L280 228Z"
                fill={"url(#" + id + "-top)"}
              />
              <path
                d="M162 162V183L280 249V228Z"
                fill={"url(#" + id + "-left)"}
              />
              <path
                d="M280 228V249L398 183V162Z"
                fill={"url(#" + id + "-right)"}
              />
              <path
                d="M162 162L280 96L398 162L280 228ZM162 162V183L280 249L398 183V162M280 228V249"
                stroke={"url(#" + id + "-edge)"}
                strokeOpacity={index === 2 ? 0.95 : 0.45}
              />
            </g>
          ))}
          <path
            d="M190 161L280 111L370 161L280 211Z"
            stroke="#b5edff"
            strokeOpacity=".65"
          />
          <path
            d="M224 161L280 130L336 161L280 192Z"
            fill="#97d8ff"
            fillOpacity=".18"
            stroke="#e4f8ff"
            strokeOpacity=".8"
          />
          <path
            d="M162 162L280 96L398 162"
            stroke="#7bdfff"
            strokeWidth="4"
            filter={"url(#" + id + "-glow)"}
          />
          <path
            d="M259 158L278 148L293 156L274 166ZM275 168L294 158L309 166L290 176Z"
            fill="#effaff"
          />
        </g>
        <g fill="#b7dcff">
          <circle cx="132" cy="245" r="2" />
          <circle cx="426" cy="202" r="2" />
          <circle cx="231" cy="63" r="1.5" />
          <circle cx="389" cy="307" r="1.5" />
        </g>
      </svg>
      <div className="sculpture-label sculpture-companies">
        <span>
          <CubeIcon />
        </span>
        <div>
          <small>THE ORGANISATIONS</small>
          <strong>Companies</strong>
        </div>
        <i />
      </div>
      <div className="sculpture-label sculpture-people">
        <span>
          <PersonIcon />
        </span>
        <div>
          <small>THE CONNECTIONS</small>
          <strong>People</strong>
        </div>
        <i />
      </div>
      <div className="sculpture-label sculpture-contracts">
        <span>
          <FileTextIcon />
        </span>
        <div>
          <small>THE CONTEXT</small>
          <strong>Contracts</strong>
        </div>
        <i />
      </div>
    </div>
  );
}
