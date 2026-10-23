import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import BlurPanel from "./BlurPanel.jsx";

const POS = {
  "Top Left": [3, 4], "Top Center": [50, 4], "Top Right": [97, 4],
  "Center Left": [3, 50], "Center": [50, 50], "Center Right": [97, 50],
  "Bottom Left": [3, 85], "Bottom Center": [50, 85], "Bottom Right": [97, 85],
};
const CYAN = "#22d3ee", GOLD = "#fbbf24", RED = "#f43f5e";
const LAYERS = [
  { k: "logo", label: "🏷️ Logo", c: CYAN, def: { pos: "Top Right", x: 97, y: 4, size: 15, op: 90 } },
  { k: "sponsor", label: "⭐ Sponsor", c: GOLD, def: { pos: "Bottom Left", x: 3, y: 85, size: 25, op: 90 } },
  { k: "overlay", label: "🖼️ Overlay", c: CYAN, def: { pos: "Bottom Center", x: 50, y: 85, size: 25, op: 90 } },
  { k: "text", label: "©️ Khmer Text", c: "#a78bfa", def: { pos: "Bottom Center", x: 50, y: 92, size: 50, op: 100 } },
];
const init = () => Object.fromEntries(LAYERS.map((L) => [L.k, { on: false, url: "", name: "", text: "", color: "#ffffff", ...L.def }]));

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
  const [st, setSt] = useState(init);
  const [tab, setTab] = useState("logo");
  const [blurTab, setBlurTab] = useState(false);
  const [busy, setBusy] = useState("");
  const [host, setHost] = useState(null);
  const [textPng, setTextPng] = useState("");
  const fileRef = useRef();
  const upd = (k, p) => setSt((s) => ({ ...s, [k]: { ...s[k], ...p } }));

  useEffect(() => {
    const t = setTimeout(() => setHost(document.querySelector("video")?.parentElement || null), 50);
    return () => clearTimeout(t);
  }, [video]);

  // វីដេអូថ្មី → លុប file layer ចាស់ (ជារបស់វីដេអូមុន) តែរក្សាការកំណត់
  useEffect(() => {
    setSt((s) => Object.fromEntries(Object.entries(s).map(([k, v]) => [k, k === "text" ? v : { ...v, url: "", name: "", on: false }])));
  }, [video?.id]);

  // អក្សរខ្មែរ → PNG (ដូច subtitle: មិនពឹង font របស់ FFmpeg)
  const T = st.text;
  useEffect(() => {
    if (!T.on || !T.text.trim()) { setTextPng(""); return; }
    let dead = false;
    (async () => {
      try { await document.fonts.load("600 64px 'Noto Sans Khmer'"); } catch { /* ប្រើ font ប្រព័ន្ធ */ }
      if (dead) return;
      const fs = 64, pad = 16, lh = Math.round(fs * 1.5);
      const font = `600 ${fs}px 'Noto Sans Khmer','Noto Sans SC',sans-serif`;
      const c = document.createElement("canvas"), ctx = c.getContext("2d");
      ctx.font = font;
      const lines = T.text.split("\n");
      c.width = Math.max(10, Math.ceil(Math.max(...lines.map((l) => ctx.measureText(l).width))) + pad * 2);
      c.height = lh * lines.length + pad;
      ctx.font = font; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.lineJoin = "round";
      ctx.lineWidth = fs * 0.16; ctx.strokeStyle = "#000"; ctx.fillStyle = T.color;
      lines.forEach((l, i) => { const y = pad / 2 + lh * i + lh / 2; ctx.strokeText(l, c.width / 2, y); ctx.fillText(l, c.width / 2, y); });
      setTextPng(c.toDataURL("image/png"));
    })();
    return () => { dead = true; };
  }, [T.on, T.text, T.color]);

  const choosePos = (k, p) => { upd(k, { pos: p }); if (POS[p]) upd(k, { x: POS[p][0], y: POS[p][1] }); };

  const pick = async (k, f) => {
    if (!f) return;
    if (!video) { alert("សូម Upload វីដេអូជាមុន"); return; }
    setBusy("upload");
    try {
      const fd = new FormData(); fd.append("file", f);
      const res = await fetch(`/api/layer?id=${video.id}&kind=${k}`, { method: "POST", body: fd });
      const j = await res.json();
      if (!res.ok) throw new Error(j.detail || "Upload បរាជ័យ");
      upd(k, { url: j.url + "?v=" + Date.now(), name: f.name, on: true });
    } catch (e) { alert(e.message); }
    finally { setBusy(""); if (fileRef.current) fileRef.current.value = ""; }
  };

  const apply = async () => {
    if (!video) { alert("សូម Upload វីដេអូជាមុន"); return; }
    setBusy("apply");
    try {
      const layers = [];
      for (const L of LAYERS) {
        const s = st[L.k]; if (!s.on) continue;
        let file = s.url;
        if (L.k === "text") {
          if (!textPng) continue;
          const fd = new FormData(); fd.append("file", await (await fetch(textPng)).blob(), "text.png");
          const r = await fetch(`/api/layer?id=${video.id}&kind=text`, { method: "POST", body: fd });
          const j = await r.json(); if (!r.ok) throw new Error(j.detail || "Upload បរាជ័យ");
          file = j.url;
        }
        if (file) layers.push({ kind: L.k, enabled: true, file, x: s.x, y: s.y, size: s.size, opacity: s.op });
      }
      if (!layers.length) throw new Error("គ្មាន layer ដែលបានបើក ឬមានរូប");
      const res = await fetch("/api/layers_apply", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: video.id, layers }) });
      const j = await res.json();
      if (!res.ok) throw new Error(j.detail || "បរាជ័យ");
      const a = document.createElement("a"); a.href = j.url; a.download = ""; a.click();
    } catch (e) { alert(e.message); }
    finally { setBusy(""); }
  };

  const previews = host ? createPortal(<>{LAYERS.map((L, i) => {
    const s = st[L.k], src = L.k === "text" ? textPng : s.url;
    if (!s.on || !src) return null;
    const isVid = /\.mp4($|\?)/i.test(src);
    const Tg = isVid ? "video" : "img";
    return <Tg key={L.k} src={src} {...(isVid ? { autoPlay: true, loop: true, muted: true, playsInline: true } : { alt: "", draggable: false })} style={{ position: "absolute", left: `${s.x}%`, top: `${s.y}%`, width: `${s.size}%`,
      transform: `translate(-${s.x}%, -${s.y}%)`, opacity: s.op / 100, pointerEvents: "none", zIndex: 5 + i }} />;
  })}</>, host) : null;

  const cur = LAYERS.find((L) => L.k === tab), s = st[tab], isText = tab === "text";
  return (
    <div className="rounded-xl p-2 text-sm shrink-0 w-full overflow-auto" style={{
      maxWidth: 900, maxHeight: 260, background: "rgba(255,255,255,.04)", border: `1px solid ${CYAN}66`, boxShadow: "0 0 14px rgba(34,211,238,.15)" }}>
      <div className="flex items-center gap-1.5 mb-1.5 flex-wrap">
        {LAYERS.map((L) => (
          <button key={L.k} onClick={() => { setTab(L.k); setBlurTab(false); }} className="rounded-lg px-2.5 py-1 text-xs font-semibold" style={{
            background: tab === L.k ? `${L.c}33` : "transparent", border: `1px solid ${tab === L.k ? L.c : "#ffffff22"}`, color: L.c }}>
            {L.label}{st[L.k].on ? " ●" : ""}
          </button>
        ))}
        <button onClick={() => setBlurTab(true)} className="rounded-lg px-2.5 py-1 text-xs font-semibold" style={{
          background: blurTab ? "#f472b633" : "transparent", border: `1px solid ${blurTab ? "#f472b6" : "#ffffff22"}`, color: "#f472b6" }}>
          🔲 Blur
        </button>
        {false && (<></>)}
        <label className="flex items-center gap-1.5 cursor-pointer ml-auto" style={{ color: cur.c, display: blurTab ? "none" : undefined }}>
          <input type="checkbox" checked={s.on} onChange={(e) => upd(tab, { on: e.target.checked })} style={{ accentColor: CYAN }} />
          <span>Enable</span>
        </label>
      </div>

      <div className={blurTab ? "hidden" : "grid gap-x-4"} style={{ gridTemplateColumns: "minmax(0,1fr) minmax(0,1fr)" }}>
        <div className="space-y-1.5 min-w-0">
          {isText ? (
            <>
              <textarea rows={2} value={s.text} onChange={(e) => upd("text", { text: e.target.value, on: true })} placeholder="វាយអក្សរខ្មែរ / English..."
                className="w-full rounded-lg px-2 py-1" style={{ background: "#1a1245", border: `1px solid ${cur.c}66`, color: "#fff" }} />
              <label className="flex items-center gap-2 text-xs"><span className="opacity-80">🎨 Color</span>
                <input type="color" value={s.color} onChange={(e) => upd("text", { color: e.target.value })} /></label>
            </>
          ) : (
            <>
              <div className="flex gap-2">
                <label className="flex-1 text-center rounded-lg py-1.5 cursor-pointer font-semibold truncate" style={{ background: `${cur.c}22`, border: `1px solid ${cur.c}`, color: cur.c }}>
                  📁 {busy === "upload" ? "កំពុង Upload..." : s.url ? "Change Asset" : "Select Asset"}
                  <input ref={fileRef} type="file" hidden accept={tab === "logo" || tab === "sponsor" ? ".png,.jpg,.jpeg,.webp,.gif,.mp4,image/png,image/jpeg,image/webp,image/gif,video/mp4" : ".png,.jpg,.jpeg,.webp,.gif,image/png,image/jpeg,image/webp,image/gif"} onChange={(e) => pick(tab, e.target.files?.[0])} />
                </label>
                <button className="rounded-lg px-3 font-semibold" onClick={() => upd(tab, { url: "", name: "", on: false })} disabled={!s.url}
                  style={{ background: "rgba(244,63,94,.12)", border: `1px solid ${RED}`, color: RED, opacity: s.url ? 1 : 0.5 }}>✕ Remove</button>
              </div>
              {s.name && <div className="text-xs truncate" style={{ color: cur.c }}>📄 {s.name}</div>}
            </>
          )}
          <label className="flex items-center gap-2 text-xs">
            <span className="opacity-80 shrink-0">📍 Position</span>
            <select value={s.pos} onChange={(e) => choosePos(tab, e.target.value)} className="flex-1 min-w-0 rounded-lg px-2 py-1"
              style={{ background: "#1a1245", border: `1px solid ${cur.c}66`, color: "#fff" }}>
              {[...Object.keys(POS), "Custom"].map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </label>
          <button className="w-full rounded-lg py-1.5 font-semibold" onClick={apply} disabled={!!busy}
            title="ចុច Export វីដេអូជាមុន រួចចុចប៊ូតុងនេះ។ Layer ទាំងអស់ដែលបានបើកត្រូវដាក់ម្តងតែមួយ (file ថ្មី មិនជំនួសវីដេអូ Export ដើម)"
            style={{ background: "rgba(251,191,36,.15)", border: `1px solid ${GOLD}`, color: GOLD }}>
            {busy === "apply" ? "កំពុងដាក់ Layers..." : "🎬 Apply Layers to Exported Video"}
          </button>
        </div>
        <div className="space-y-1 min-w-0">
          <Slider label="X (%)" value={s.x} set={(v) => upd(tab, { x: v, pos: "Custom" })} />
          <Slider label="Y (%)" value={s.y} set={(v) => upd(tab, { y: v, pos: "Custom" })} />
          <Slider label="Size (%)" value={s.size} set={(v) => upd(tab, { size: v })} min={1} />
          <Slider label="Opacity (%)" value={s.op} set={(v) => upd(tab, { op: v })} />
        </div>
      </div>
      {blurTab && <BlurPanel video={video} host={host} />}
      {previews}
    </div>
  );
}
