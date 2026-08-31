import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { adoptCredentialFromUrl } from "./storage";
import "./index.css";

adoptCredentialFromUrl(window.location, window.history);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
