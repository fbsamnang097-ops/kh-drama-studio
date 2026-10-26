import { useEffect, useState } from "react";

const KEY = "khds-ios-install-tip-dismissed";

function isIOS() {
  const ua = navigator.userAgent || "";
  return /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}

function isInstalled() {
  return navigator.standalone === true || window.matchMedia?.("(display-mode: standalone)").matches;
}

export default function InstallHint() {
  const [show, setShow] = useState(false);
  useEffect(() => {
    try { setShow(isIOS() && !isInstalled() && localStorage.getItem(KEY) !== "1"); }
    catch { setShow(isIOS() && !isInstalled()); }
  }, []);
  if (!show) return null;
  const dismiss = () => {
    setShow(false);
    try { localStorage.setItem(KEY, "1"); } catch { /* private browsing */ }
  };
  return (
    <aside className="ios-install-tip" role="note" aria-label="ដំឡើង KH Drama Studio លើ iPhone">
      <span className="ios-install-tip-icon" aria-hidden="true">＋</span>
      <span><b>ដំឡើងលើ iPhone</b><small>ចុច Share ⬆ → Add to Home Screen</small></span>
      <button type="button" onClick={dismiss} aria-label="បិទ">×</button>
    </aside>
  );
}
