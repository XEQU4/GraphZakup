import { Link, type LinkProps } from "react-router-dom";
import { useBorderGlow } from "./BorderGlow";

/** Keep the whole saved-group card a native, keyboard-accessible link. */
export function BorderGlowLink({
  to,
  state,
  className = "",
  children,
}: Pick<LinkProps, "to" | "state" | "className" | "children">) {
  const { surfaceProps, decoration } = useBorderGlow<HTMLAnchorElement>();
  return (
    <Link
      {...surfaceProps}
      to={to}
      state={state}
      className={`${surfaceProps.className} ${className}`}
    >
      {decoration}
      {children}
    </Link>
  );
}
