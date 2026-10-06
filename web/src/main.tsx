import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "./design-system/fonts.css";
import "./design-system/tokens.css";
import "./design-system/base.css";
import { App } from "./app/App";
import * as auth from "./features/auth/api"; // TEMP: remove after verifying Phase C

(window as unknown as { auth: typeof auth }).auth = auth; // TEMP: remove after verifying Phase C

const container = document.getElementById("root");
if (!container) throw new Error("Root element #root is missing from index.html");

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
