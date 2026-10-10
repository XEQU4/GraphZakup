/** IZ monogram joined by two evidence points. Shared by header and footer. */
export function BrandMark() {
  return (
    <svg viewBox="0 0 40 40" fill="none" aria-hidden="true">
      <path d="M8 10V30" stroke="currentColor" strokeWidth="4" />
      <path
        d="M17 10H32L17 30H32"
        stroke="currentColor"
        strokeWidth="4"
        strokeLinejoin="bevel"
      />
      <path
        className="brand-connection"
        d="M8 6V10M32 30V34M8 30L17 30"
        stroke="#5797f0"
        strokeWidth="1.5"
      />
      <circle cx="8" cy="6" r="2" fill="#5797f0" />
      <circle cx="32" cy="34" r="2" fill="#5797f0" />
    </svg>
  );
}
