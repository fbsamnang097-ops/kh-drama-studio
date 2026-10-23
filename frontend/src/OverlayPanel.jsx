import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";

// ទីតាំងបឋម [X%, Y%] (ដូច FFmpeg: X/Y គិតពីកន្លែងទំនេរ)
const POS = {
  "Top Left": [3, 4], "Top Center": [50, 4], "Top Right": [97, 4],
  "Center Left": [3, 50], "Center": [50, 50], "Center Right": [97, 50],
  "Bottom Left": [3, 85], "Bottom Center": [50, 85], "Bottom Right": [97, 85],
};
const CYAN = "#22d3ee", GOLD = "#fbbf24", RED = "#f43f5e";

function Slider({ label, value, set, min = 0, max = 100 }) {
  return (
    <div className="grid items-center gap-2" style={{ gridTemplateColumns: "64px 1fr 44px" }}>
      <span className="text-xs opacity-80">{label}</span>
      <input type="range" min={min} max={max} step={1} value={value} onChange={(e) => set(+e.target.value)}
        style={{ accentColor: CYAN, filter: "drop-shadow(0 0 4px rgba(34,211,238,.7))" }} />
      <span className="text-xs text-right font-semibold" style={{ color: CYAN }}>{value}%</span>
    </div>
  );
}

export default function OverlayPanel({ video }) {
  const [on, setOn] = useState(false);
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [pos, setPos] = useState("Bottom Center");
  const [x, setX] = useState(50);
  const [y, setY] = useState(85);
  const [size, setSize] = useState(25);
  const [op, setOp] = useState(90);
  const [busy, setBusy] = useState("");
  const [host, setHost] = useState(null);
  const fileRef = useRef();

  // រកប្រអប់ preview វីដេអូ ដើម្បីដាក់ overlay ពីលើ
  useEffect(() => {
    const t = setTimeout(() => setHost(document.querySelector("video")?.parentElement || null), 50);
    return () => clearTimeout(t);
  }, [video]);

  const choosePos = (p) => { setPos(p); if (POS[p]) { setX(POS[p][0]); setY(POS[p][1]); } };

  const pick = async (f) => {
    if (!f) return;
    if (!video) { alert("សូម Upload វីដេអូជាមុន"); return; }
    setBusy("upload");
    try {
      const fd = new FormData(); fd.append("file", f);
      const res = await fetch("/api/overlay?id=" + video.id, { method: "POST", body: fd });
      const j = await res.json();
      if (!res.ok) throw new Error(j.detail || "Upload បរាជ័យ");
      setUrl(j.url + "?v=" + Date.now()); setName(f.name); setOn(true);
    } catch (e) { alert(e.message); }
    finally { setBusy(""); if (fileRef.current) fileRef.current.value = ""; }
  };

  const remove = () => { setUrl(""); setName(""); setOn(false); };

  const apply = async () => {
    if (!video) { alert("សូម Upload វីដេអូជាមុន"); return; }
    setBusy("apply");
    try {
      const res = await fetch("/api/overlay_apply", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: video.id, overlay: { enabled: on, file: url, x, y, size, opacity: op } }),
      });
      const j = await res.json();
      if (!res.ok) throw new Error(j.detail || "បរាជ័យ");
      const a = document.createElement("a"); a.href = j.url; a.download = ""; a.click();
    } catch (e) { alert(e.message); }
    finally { setBusy(""); }
  };

  const preview = host && on && url ? createPortal(
    <img src={url} alt="" draggable={false} style={{
      position: "absolute", left: `${x}%`, top: `${y}%`, width: `${size}%`,
      transform: `translate(-${x}%, -${y}%)`, opacity: op / 100, pointerEvents: "none", zIndex: 5,
    }} />, host) : null;

  return (
    <div className="rounded-xl p-3 space-y-2 text-sm" style={{
      background: "rgba(255,255,255,.04)", border: `1px solid ${CYAN}66`, boxShadow: "0 0 14px rgba(34,211,238,.15)" }}>
      <div className="font-semibold" style={{ color: GOLD }}>🖼️ Custom Overlay / Animated Banner</div>

      <label className="flex items-center gap-2 cursor-pointer">
        <input type="checkbox" checked={on} onChange={(e) => setOn(e.target.checked)} style={{ accentColor: CYAN }} />
        <span>Enable Overlay</span>
      </label>

      <div className="flex gap-2">
        <label className="flex-1 text-center rounded-lg py-2 cursor-pointer font-semibold" style={{
          background: "rgba(34,211,238,.15)", border: `1px solid ${CYAN}`, color: CYAN }}>
          📁 {busy === "upload" ? "កំពុង Upload..." : url ? "Change Asset" : "Select Asset"}
          <input ref={fileRef} type="file" hidden accept=".png,.jpg,.jpeg,.webp,.gif,image/png,image/jpeg,image/webp,image/gif"
            onChange={(e) => pick(e.target.files?.[0])} />
        </label>
        <button className="rounded-lg px-3 font-semibold" onClick={remove} disabled={!url}
          style={{ background: "rgba(244,63,94,.12)", border: `1px solid ${RED}`, color: RED, opacity: url ? 1 : 0.5 }}>
          ✕ Remove
        </button>
      </div>
      {name && <div className="text-xs truncate" style={{ color: CYAN }}>📄 {name}</div>}

      <label className="flex items-center gap-2 text-xs">
        <span className="opacity-80" style={{ width: 64 }}>📍 Position</span>
        <select value={pos} onChange={(e) => choosePos(e.target.value)} className="flex-1 rounded-lg px-2 py-1"
          style={{ background: "#1a1245", border: `1px solid ${CYAN}66`, color: "#fff" }}>
          {[...Object.keys(POS), "Custom"].map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
      </label>

      <Slider label="X (%)" value={x} set={(v) => { setX(v); setPos("Custom"); }} />
      <Slider label="Y (%)" value={y} set={(v) => { setY(v); setPos("Custom"); }} />
      <Slider label="Size (%)" value={size} set={setSize} min={1} />
      <Slider label="Opacity (%)" value={op} set={setOp} />

      <button className="w-full rounded-lg py-2 font-semibold" onClick={apply} disabled={!url || !on || !!busy}
        style={{ background: "rgba(251,191,36,.15)", border: `1px solid ${GOLD}`, color: GOLD, opacity: url && on ? 1 : 0.5 }}>
        {busy === "apply" ? "កំពុងដាក់ Overlay..." : "🎬 Apply Overlay to Exported Video"}
      </button>
      <div className="text-xs opacity-60">ចុច Export វីដេអូជាមុន រួចចុចប៊ូតុងនេះ។ លទ្ធផលជា file ថ្មី (មិនជំនួសវីដេអូ Export ដើម)។</div>
      {preview}
    </div>
  );
}
