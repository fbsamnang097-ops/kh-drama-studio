import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";

const PINK = "#f472b6", RED = "#f43f5e", GOLD = "#fbbf24", CYAN = "#22d3ee";
const newBox = () => ({ id: Date.now() + Math.random(), x: 50, y: 50, w: 20, h: 15, strength: 25, start: 0, end: 9999, follow: false, kf: [] });

function posAt(b, t) {
  const k = [...b.kf].sort((a, c) => a.t - c.t);
  if (!b.follow || !k.length) return [b.x, b.y];
  if (t <= k[0].t) return [k[0].x, k[0].y];
  for (let i = 0; i < k.length - 1; i++) {
    if (t < k[i + 1].t) {
      const f = (t - k[i].t) / Math.max(k[i + 1].t - k[i].t, 0.001);
      return [k[i].x + (k[i + 1].x - k[i].x) * f, k[i].y + (k[i + 1].y - k[i].y) * f];
    }
  }
  const l = k[k.length - 1]; return [l.x, l.y];
}

function Slider({ label, value, set, min = 0, max = 100, unit = "%" }) {
  return (
    <div className="grid items-center gap-2" style={{ gridTemplateColumns: "64px 1fr 44px" }}>
      <span className="text-xs opacity-80">{label}</span>
      <input type="range" min={min} max={max} step={1} value={value} onChange={(e) => set(+e.target.value)} style={{ accentColor: PINK }} />
      <span className="text-xs text-right font-semibold" style={{ color: PINK }}>{Math.round(value)}{unit}</span>
    </div>
  );
}

export default function BlurPanel({ video, host }) {
  const [boxes, setBoxes] = useState([]);
  const [sel, setSel] = useState(null);
  const [t, setT] = useState(0);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const iv = setInterval(() => { const v = document.querySelector("video"); if (v) setT(v.currentTime || 0); }, 100);
    return () => clearInterval(iv);
  }, []);
  useEffect(() => { setBoxes([]); setSel(null); }, [video?.id]);

  const cur = boxes.find((b) => b.id === sel) || null;
  const upd = (id, p) => setBoxes((bs) => bs.map((b) => (b.id === id ? { ...b, ...p } : b)));
  const nowT = () => +(document.querySelector("video")?.currentTime || 0).toFixed(2);

  // រំកិល X/Y ពេល Follow → ដាក់/ជំនួស keyframe ត្រង់ពេលបច្ចុប្បន្ន
  const move = (key, v) => {
    if (!cur) return;
    const p = { [key]: v };
    if (cur.follow) {
      const tt = nowT(), [px, py] = posAt(cur, tt);
      const k = { t: tt, x: px, y: py, [key]: v };
      p.kf = [...cur.kf.filter((q) => Math.abs(q.t - tt) > 0.15), k].sort((a, c) => a.t - c.t);
    }
    upd(cur.id, p);
  };
  const add = () => { const b = newBox(); setBoxes((bs) => [...bs, b]); setSel(b.id); };
  const del = () => { setBoxes((bs) => bs.filter((b) => b.id !== sel)); setSel(null); };

  const apply = async () => {
    if (!video) { alert("សូម Upload វីដេអូជាមុន"); return; }
    if (!boxes.length) { alert("សូមបន្ថែម Blur box ជាមុន"); return; }
    setBusy(true);
    try {
      const res = await fetch("/api/blur_apply", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: video.id, boxes: boxes.map(({ id, ...b }) => b) }) });
      const j = await res.json();
      if (!res.ok) throw new Error(j.detail || "បរាជ័យ");
      const a = document.createElement("a"); a.href = j.url; a.download = ""; a.click();
    } catch (e) { alert(e.message); }
    finally { setBusy(false); }
  };

  const drag = useRef(null);
  const movePos = (id, nx, ny) => setBoxes((bs) => bs.map((b) => {
    if (b.id !== id) return b;
    nx = Math.max(0, Math.min(100, nx)); ny = Math.max(0, Math.min(100, ny));
    if (!b.follow) return { ...b, x: nx, y: ny };
    const tt = nowT();
    return { ...b, kf: [...b.kf.filter((q) => Math.abs(q.t - tt) > 0.15), { t: tt, x: nx, y: ny }].sort((a, c) => a.t - c.t) };
  }));
  const startDrag = (e, b, mode) => {
    e.preventDefault(); e.stopPropagation();
    setSel(b.id);
    document.querySelector("video")?.pause();
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = { id: b.id, mode, rect: host.getBoundingClientRect() };
  };
  const onDrag = (e) => {
    const d = drag.current; if (!d) return;
    const px = ((e.clientX - d.rect.left) / d.rect.width) * 100, py = ((e.clientY - d.rect.top) / d.rect.height) * 100;
    if (d.mode === "move") { movePos(d.id, px, py); return; }
    setBoxes((bs) => bs.map((b) => {
      if (b.id !== d.id) return b;
      const [cx, cy] = posAt(b, nowT());
      return { ...b, w: Math.max(2, Math.min(100, 2 * Math.abs(px - cx))), h: Math.max(2, Math.min(100, 2 * Math.abs(py - cy))) };
    }));
  };
  const endDrag = () => { drag.current = null; };

  const prev = host ? createPortal(<>{boxes.map((b) => {
    if (t < b.start || t > b.end) return null;
    const [cx, cy] = posAt(b, t);
    return <div key={b.id}
      onPointerDown={(e) => startDrag(e, b, "move")} onPointerMove={onDrag} onPointerUp={endDrag} onPointerCancel={endDrag}
      style={{ position: "absolute", left: `${cx}%`, top: `${cy}%`, width: `${b.w}%`, height: `${b.h}%`,
      transform: "translate(-50%,-50%)", backdropFilter: `blur(${b.strength / 3}px)`, WebkitBackdropFilter: `blur(${b.strength / 3}px)`,
      border: `1px dashed ${b.id === sel ? GOLD : PINK}`, pointerEvents: "auto", cursor: "move", touchAction: "none", zIndex: 20 }}>
      <div onPointerDown={(e) => startDrag(e, b, "resize")}
        style={{ position: "absolute", right: -6, bottom: -6, width: 14, height: 14, background: GOLD, borderRadius: 3,
        cursor: "nwse-resize", touchAction: "none" }} />
    </div>;
  })}</>, host) : null;

  return (
    <div>
      <div className="flex items-center gap-1.5 mb-1.5 flex-wrap">
        <button className="rounded-lg px-2.5 py-1 text-xs font-semibold" onClick={add}
          style={{ background: `${PINK}22`, border: `1px solid ${PINK}`, color: PINK }}>➕ Add Blur Box</button>
        {boxes.map((b, i) => (
          <button key={b.id} onClick={() => setSel(b.id)} className="rounded-lg px-2 py-1 text-xs"
            style={{ border: `1px solid ${b.id === sel ? GOLD : "#ffffff22"}`, color: b.id === sel ? GOLD : "#fff" }}>Blur {i + 1}</button>
        ))}
        {cur && <button className="rounded-lg px-2 py-1 text-xs ml-auto" onClick={del}
          style={{ background: "rgba(244,63,94,.12)", border: `1px solid ${RED}`, color: RED }}>✕ Remove</button>}
      </div>

      {!cur ? <div className="text-xs opacity-70 py-2">ចុច “Add Blur Box” ដើម្បីចាប់ផ្តើម។</div> : (
        <div className="grid gap-x-4" style={{ gridTemplateColumns: "minmax(0,1fr) minmax(0,1fr)" }}>
          <div className="space-y-1 min-w-0">
            <Slider label="X (%)" value={posAt(cur, t)[0]} set={(v) => move("x", v)} />
            <Slider label="Y (%)" value={posAt(cur, t)[1]} set={(v) => move("y", v)} />
            <Slider label="Width" value={cur.w} set={(v) => upd(cur.id, { w: v })} min={2} />
            <Slider label="Height" value={cur.h} set={(v) => upd(cur.id, { h: v })} min={2} />
            <Slider label="Blur" value={cur.strength} set={(v) => upd(cur.id, { strength: v })} min={2} max={80} unit="" />
          </div>
          <div className="space-y-1.5 min-w-0 text-xs">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={cur.follow} style={{ accentColor: PINK }}
                onChange={(e) => upd(cur.id, { follow: e.target.checked, kf: e.target.checked && !cur.kf.length ? [{ t: nowT(), x: cur.x, y: cur.y }] : cur.kf })} />
              <span>🎯 Follow motion (keyframes)</span>
            </label>
            {cur.follow && (
              <div className="opacity-80">Play ទៅចំណុចផ្សេង រួចរំកិល X/Y តាមវត្ថុ → keyframe ត្រូវបានចាប់ស្វ័យប្រវត្តិ
                <div className="flex flex-wrap gap-1 mt-1">
                  {cur.kf.map((k, i) => (
                    <button key={i} onClick={() => upd(cur.id, { kf: cur.kf.filter((_, j) => j !== i) })} title="ចុចដើម្បីលុប"
                      className="rounded px-1.5 py-0.5" style={{ border: `1px solid ${PINK}66`, color: PINK }}>{k.t.toFixed(1)}s ✕</button>
                  ))}
                </div>
              </div>
            )}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="opacity-80">⏱ ពេល</span>
              <button className="rounded px-2 py-0.5" onClick={() => upd(cur.id, { start: nowT() })} style={{ border: `1px solid ${CYAN}`, color: CYAN }}>Start = ឥឡូវ</button>
              <span>{cur.start.toFixed(1)}s</span>
              <button className="rounded px-2 py-0.5" onClick={() => upd(cur.id, { end: nowT() })} style={{ border: `1px solid ${CYAN}`, color: CYAN }}>End = ឥឡូវ</button>
              <span>{cur.end >= 9999 ? "ដល់ចប់" : cur.end.toFixed(1) + "s"}</span>
            </div>
          </div>
        </div>
      )}
      <button className="w-full rounded-lg py-1.5 font-semibold mt-1.5" onClick={apply} disabled={busy || !boxes.length}
        title="ចុច Export វីដេអូជាមុន រួចចុចប៊ូតុងនេះ។ បើបាន Apply Layers រួច Blur នឹងដាក់លើលទ្ធផលនោះ"
        style={{ background: "rgba(251,191,36,.15)", border: `1px solid ${GOLD}`, color: GOLD, opacity: boxes.length ? 1 : 0.5 }}>
        {busy ? "កំពុងដាក់ Blur..." : "🔲 Apply Blur to Exported Video"}
      </button>
      {prev}
    </div>
  );
}
