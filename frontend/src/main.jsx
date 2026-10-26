import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import InstallHint from "./InstallHint.jsx";

createRoot(document.getElementById("root")).render(<><App /><InstallHint /></>);

if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost")) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {});
  });
}
