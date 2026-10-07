// Adapted manual-focus corner treatment from React Bits True Focus.
// MIT + Commons Clause; full notice in licenses/react-bits.txt.
import { motion } from "motion/react";
import { useMotionPreferences } from "../MotionPreferences";

export function FocusFrame({ scope }: { scope: string }) {
  const { enabled } = useMotionPreferences();
  return (
    <motion.span
      className="nav-focus-frame"
      layoutId={scope + "-focus-frame"}
      transition={{ duration: enabled ? 0.28 : 0, ease: "easeOut" }}
      aria-hidden="true"
    >
      <i className="focus-corner top-left" />
      <i className="focus-corner top-right" />
      <i className="focus-corner bottom-left" />
      <i className="focus-corner bottom-right" />
    </motion.span>
  );
}
