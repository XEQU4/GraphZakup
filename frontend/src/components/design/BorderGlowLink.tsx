import { Link, type LinkProps } from "react-router-dom";
import { useBorderGlow } from "./BorderGlow";

/** Keep the whole saved-group card a native, keyboard-accessible link. */
export function BorderGlowLink({
  to,
  className = "",
  children,
}: Pick<LinkProps, "to" | "className" | "children">) {
  const { surfaceProps, decoration } = useBorderGlow<HTMLAnchorElement>();
  return (
    <Link
      {...surfaceProps}
      to={to}
      className={`${surfaceProps.className} ${className}`}
    >
      {decoration}
      {children}
    </Link>
  );
}
