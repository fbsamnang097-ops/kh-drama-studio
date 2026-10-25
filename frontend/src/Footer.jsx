import { useState, useEffect } from "react";
import { createPortal } from "react-dom";

export default function Footer() {
  const [v, setV] = useState("");
  const [stale, setStale] = useState(false);
  useEffect(() => {
    fetch("/api/version").then((r) => r.json())
      .then((j) => { setV(j.version || ""); setStale(!!j.ui?.stale); })
      .catch(() => {});
  }, []);
  const ver = v ? (/^\d/.test(v) ? `v${v} ` : `${v} `) : "";
  return createPortal(
    <div style={{ position: "fixed", left: 0, right: 0, bottom: 0, textAlign: "center", fontSize: 11, lineHeight: "18px",
      padding: "0 8px", color: "rgba(255,255,255,.6)", background: "rgba(10,6,40,.55)", pointerEvents: "none", zIndex: 5 }}>
      {stale && (
        <span title="frontend/dist ចាស់ជាង frontend/src · rebuild: cd frontend && npm run build"
          style={{ color: "#fff", background: "#f43f5e", padding: "1px 8px", borderRadius: 999, marginRight: 6, fontWeight: 700 }}>
          ⚠ UI ចាស់ — rebuild
        </span>
      )}
      {ver}© {new Date().getFullYear()} KH Drama Studio · រក្សាសិទ្ធិគ្រប់យ៉ាង
    </div>, document.body);
}
