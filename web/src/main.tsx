import "@fontsource-variable/public-sans";
import "@fontsource/red-hat-mono/400.css";
import "@fontsource/red-hat-mono/600.css";
import "./styles.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";

const saved = (() => {
  try {
    return window.localStorage.getItem("libertas.display");
  } catch {
    return null;
  }
})();
document.documentElement.dataset.display = saved === "projector" ? "projector" : "desk";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
