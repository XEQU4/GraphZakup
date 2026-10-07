import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
const Context = createContext({
  enabled: true,
  toggle: () => {},
  reduced: false,
});
export function MotionPreferences({ children }: { children: ReactNode }) {
  const [reduced, setReduced] = useState(
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  const [allowed, setAllowed] = useState(() => {
    try {
      return localStorage.getItem("iz2.motion-enabled.v1") !== "false";
    } catch {
      return true;
    }
  });
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const change = () => setReduced(media.matches);
    media.addEventListener("change", change);
    return () => media.removeEventListener("change", change);
  }, []);
  const enabled = allowed && !reduced;
  useEffect(() => {
    document.documentElement.dataset.motion = enabled ? "on" : "off";
  }, [enabled]);
  const toggle = () =>
    setAllowed((previous) => {
      try {
        localStorage.setItem("iz2.motion-enabled.v1", String(!previous));
      } catch {}
      return !previous;
    });
  return (
    <Context.Provider value={{ enabled, toggle, reduced }}>
      {children}
    </Context.Provider>
  );
}
export const useMotionPreferences = () => useContext(Context);
