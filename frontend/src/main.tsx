import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { DisplayModeProvider } from "@/lib/display-mode";
import { StyleGuide } from "@/routes/StyleGuide";
import "./index.css";

const container = document.getElementById("root");
if (!container) {
  throw new Error("Root element #root not found");
}

createRoot(container).render(
  <StrictMode>
    <DisplayModeProvider>
      <StyleGuide />
    </DisplayModeProvider>
  </StrictMode>,
);
