import "./design-system/fonts.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "./design-system/tokens.css";
import "./design-system/base.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app/App";
import { LazyCommandCentre } from "./app/LazyCommandCentre";

const container = document.getElementById("root");
if (!container) throw new Error("Root element #root is missing from index.html");

// The dashboard is where people land. Its code starts downloading now, alongside the session
// request, instead of only after the session answers.
if (window.location.pathname.startsWith("/w/")) {
  LazyCommandCentre.preload().catch(() => undefined);
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
