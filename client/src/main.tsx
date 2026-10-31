import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";
import { warmUpBackend } from "@/lib/fetchWithTimeout";

// Wake Render backend early so Reviews/Reimagined don't sit on loading state
warmUpBackend(import.meta.env.VITE_API_BASE_URL || "");

createRoot(document.getElementById("root")!).render(<App />);
