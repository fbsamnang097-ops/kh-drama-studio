import { useState, useEffect } from "react";
import { createPortal } from "react-dom";

export default function Footer() {
  const [v, setV] = useState("");
  useEffect(() => {
    fetch("/api/version").then((r) => r.json()).then((j) => setV(j.version || "")).catch(() => {});
  }, []);
  const ver = v ? (/^\d/.test(v) ? `v${v} ` : `${v} `) : "";
  return createPortal(
    <div style={{ position: "fixed", left: 0, right: 0, bottom: 0, textAlign: "center", fontSize: 11, lineHeight: "18px",
      padding: "0 8px", color: "rgba(255,255,255,.6)", background: "rgba(10,6,40,.55)", pointerEvents: "none", zIndex: 5 }}>
      {ver}© {new Date().getFullYear()} KH Drama Studio · រក្សាសិទ្ធិគ្រប់យ៉ាង
    </div>, document.body);
}
