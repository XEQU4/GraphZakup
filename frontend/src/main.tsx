import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { MotionConfig } from "motion/react";
import "@fontsource-variable/manrope";
import "@fontsource-variable/space-grotesk";
import "@fontsource/ibm-plex-mono/400.css";
import "./styles.css";
import App from "./App";
import "./design.css";
import "./identity.css";
import "./layout-fixes.css";
import "./control-motion.css";
import "./input-focus.css";
import { SessionProvider } from "./components/Session";
import { MotionPreferences } from "./components/MotionPreferences";
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter basename={import.meta.env.DEV ? "" : "/app"}>
      <MotionConfig reducedMotion="user">
        <MotionPreferences>
          <SessionProvider>
            <App />
          </SessionProvider>
        </MotionPreferences>
      </MotionConfig>
    </BrowserRouter>
  </React.StrictMode>,
);
