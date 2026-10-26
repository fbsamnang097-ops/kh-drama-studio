import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import BlurPanel from "./BlurPanel.jsx";
import Footer from "./Footer.jsx";
import { LAYERS, POS, CYAN, GOLD, RED, PINK } from "./layers.js";
import { renderTextPng } from "./textPix.js";

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

// st = layer ទាំង ៤ (App កាន់ state ដើម្បីឱ្យ Export បញ្ចូលបានទាំងអស់ក្នុងពេលតែមួយ)
export default function OverlayPanel({ video, layers: st, setLayers: setSt, boxes, setBoxes, onApply }) {
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

  // អក្សរខ្មែរ → PNG (preview + Export ប្រើ PNG តែមួយ)
  const T = st.text;
  useEffect(() => {
    let dead = false;
    if (!T.on || !T.text.trim()) { setTextPng(""); return; }
    (async () => {
      const url = await renderTextPng(T.text, T.color, 1080, T.size);
      if (!dead) setTextPng(url);
    })();
    return () => { dead = true; };
  }, [T.on, T.text, T.color, T.size]);

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
    setBusy("apply");
    try { await onApply(); } finally { setBusy(""); }
  };

  const previews = host ? createPortal(<>{LAYERS.map((L, i) => {
    const s = st[L.k], src = L.k === "text" ? textPng : s.url;
    if (!s.on || !src) return null;
    const isVid = /\.(mp4|mov|webm|mkv)($|\?)/i.test(src);
    const Tg = isVid ? "video" : "img";
    return <Tg key={L.k} src={src} {...(isVid ? { autoPlay: true, loop: true, muted: true, playsInline: true } : { alt: "", draggable: false })} style={{ position: "absolute", left: `${s.x}%`, top: `${s.y}%`, width: `${s.size}%`,
      transform: `translate(-${s.x}%, -${s.y}%)`, opacity: s.op / 100, pointerEvents: "none", zIndex: 5 + i }} />;
  })}</>, host) : null;

  const cur = LAYERS.find((L) => L.k === tab), s = st[tab], isText = tab === "text";
  const onCount = LAYERS.filter((L) => st[L.k].on).length + (boxes.length ? 1 : 0);
  return (
    <div className="overlay-panel rounded-xl p-2 text-sm shrink-0 w-full overflow-auto" style={{
      maxWidth: 900, maxHeight: 300, background: "rgba(255,255,255,.04)", border: `1px solid ${CYAN}66`, boxShadow: "0 0 14px rgba(34,211,238,.15)" }}>
      <div className="text-xs opacity-80 mb-1.5">
        🎬 Logo · Sponsor · Overlay · Khmer Text · Blur — <b style={{ color: GOLD }}>បញ្ចូលក្នុង Export ស្វ័យប្រវត្តិ</b> (មិនត្រូវ Apply ដោយឡែកទេ)
      </div>
      <div className="flex items-center gap-1.5 mb-1.5 flex-wrap">
        {LAYERS.map((L) => (
          <button key={L.k} onClick={() => { setTab(L.k); setBlurTab(false); }} className="rounded-lg px-2.5 py-1 text-xs font-semibold" style={{
            background: tab === L.k && !blurTab ? `${L.c}33` : "transparent", border: `1px solid ${tab === L.k && !blurTab ? L.c : "#ffffff22"}`, color: L.c }}>
            {L.label}{st[L.k].on ? " ●" : ""}
          </button>
        ))}
        <button onClick={() => setBlurTab(true)} className="rounded-lg px-2.5 py-1 text-xs font-semibold" style={{
          background: blurTab ? `${PINK}33` : "transparent", border: `1px solid ${blurTab ? PINK : "#ffffff22"}`, color: PINK }}>
          🔲 Blur{boxes.length ? ` (${boxes.length})` : ""}
        </button>
        {!blurTab && (
          <label className="flex items-center gap-1.5 cursor-pointer ml-auto" style={{ color: cur.c }}>
            <input type="checkbox" checked={s.on} onChange={(e) => upd(tab, { on: e.target.checked })} style={{ accentColor: CYAN }} />
            <span>Enable</span>
          </label>
        )}
      </div>

      <div className={`overlay-controls-grid ${blurTab ? "hidden" : "grid gap-x-4"}`} style={{ gridTemplateColumns: "minmax(0,1fr) minmax(0,1fr)" }}>
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
          <button className="w-full rounded-lg py-1.5 font-semibold" onClick={apply} disabled={!!busy || !onCount}
            title="បើបាន Export រួច ហើយចង់បន្ថែម/កែ layer និង blur ដោយមិន Export សំឡេងឡើងវិញ — ចុចប៊ូតុងនេះ (pass តែមួយ ដាក់ទាំង Layers និង Blur)"
            style={{ background: "rgba(251,191,36,.15)", border: `1px solid ${GOLD}`, color: GOLD, opacity: onCount ? 1 : 0.5 }}>
            {busy === "apply" ? "កំពុងដាក់ Layers + Blur..." : "🎬 Apply Layers + Blur លើវីដេអូ Export រួច"}
          </button>
        </div>
        <div className="space-y-1 min-w-0">
          <Slider label="X (%)" value={s.x} set={(v) => upd(tab, { x: v, pos: "Custom" })} />
          <Slider label="Y (%)" value={s.y} set={(v) => upd(tab, { y: v, pos: "Custom" })} />
          <Slider label="Size (%)" value={s.size} set={(v) => upd(tab, { size: v })} min={1} />
          <Slider label="Opacity (%)" value={s.op} set={(v) => upd(tab, { op: v })} />
        </div>
      </div>
      {blurTab && <BlurPanel video={video} host={host} boxes={boxes} setBoxes={setBoxes} onApply={apply} busy={busy} />}
      <Footer />
      {previews}
    </div>
  );
}
