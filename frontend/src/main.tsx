import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { MotionConfig } from "motion/react";
import "@fontsource-variable/manrope";
import "@fontsource-variable/space-grotesk";
import "@fontsource/ibm-plex-mono/400.css";
import "./styles/base.css";
import App from "./App";
import "./styles/design.css";
import "./styles/identity.css";
import "./styles/layout-fixes.css";
import "./styles/control-motion.css";
import "./styles/input-focus.css";
import "./styles/refinement.css";
import "./i18n/localization.css";
import { LanguageProvider } from "./i18n";
import { SessionProvider } from "./components/Session";
import { MotionPreferences } from "./components/MotionPreferences";
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <LanguageProvider>
      <BrowserRouter basename={import.meta.env.DEV ? "" : "/app"}>
        <MotionConfig reducedMotion="user">
          <MotionPreferences>
            <SessionProvider>
              <App />
            </SessionProvider>
          </MotionPreferences>
        </MotionConfig>
      </BrowserRouter>
    </LanguageProvider>
  </React.StrictMode>,
);
