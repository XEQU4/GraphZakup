import { useEffect, useRef, useState } from "react";
import { useMotionPreferences } from "../MotionPreferences";

/** Shared permission for decorative motion; no timer runs while inactive. */
export function useDecorationActive<T extends HTMLElement>(enabled = true) {
  const ref = useRef<T | null>(null);
  const { enabled: allowed } = useMotionPreferences();
  const [visible, setVisible] = useState(false);
  const [documentVisible, setDocumentVisible] = useState(
    () => !document.hidden,
  );
  useEffect(() => {
    const target = ref.current;
    if (!target) return;
    const updateDocument = () => setDocumentVisible(!document.hidden);
    updateDocument();
    document.addEventListener("visibilitychange", updateDocument);
    const observer =
      typeof IntersectionObserver === "undefined"
        ? null
        : new IntersectionObserver(
            ([entry]) => setVisible(entry.isIntersecting),
            { threshold: 0 },
          );
    if (observer) observer.observe(target);
    else setVisible(true);
    return () => {
      observer?.disconnect();
      document.removeEventListener("visibilitychange", updateDocument);
    };
  }, []);
  return { ref, active: enabled && allowed && visible && documentVisible };
}
