import { createPortal } from "react-dom";
import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import OverlayPanel from "./OverlayPanel.jsx";
import { LAYERS, initLayers, resetLayers } from "./layers.js";
import { renderTextPng } from "./textPix.js";

const api = async (path, body, isForm) => {
  const r = await fetch(path, body ? { method: "POST", ...(isForm ? { body } : { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }) } : undefined);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.detail || "កំហុស");
  return j;
};
const tc = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${(s % 60).toFixed(1).padStart(4, "0")}`;
// តួអង្គ ៧ ប្រភេទ → សំឡេងខុសៗគ្នា (ស្រី = ស្រី · ប្រុស = ប្រុស · ចាស់ · ក្មេង)
const CHARS = [
  ["男主", "👨 ប្រុស", "#38bdf8"], ["女主", "👩 ស្រី", "#f472b6"],
  ["老男", "👴 ចាស់ប្រុស", "#f59e0b"], ["老女", "👵 ចាស់ស្រី", "#fb7185"],
  ["小孩", "🧒 ក្មេង", "#34d399"], ["小孩男", "👦 ក្មេងប្រុស", "#22d3ee"],
  ["旁白", "📖 អ្នកនិទាន", "#fbbf24"],
];
const CHAR_COLOR = Object.fromEntries(CHARS.map(([k, , c]) => [k, c]));
const CHAR_LABEL = Object.fromEntries(CHARS.map(([k, l]) => [k, l]));
const CC = (c) => CHAR_COLOR[c] || "#a78bfa";   // ពណ៌តាមតួអង្គ
const STEP_C = ["#f472b6", "#fb923c", "#fbbf24", "#34d399", "#22d3ee"];
const wrapText = (ctx, text, maxW) => {
  const parts = typeof Intl !== "undefined" && Intl.Segmenter ? [...new Intl.Segmenter("km", { granularity: "word" }).segment(text)].map((x) => x.segment) : text.split(/(?<=\s)/);
  const lines = []; let cur = "";
  for (const w of parts) { const t = cur + w; if (cur && ctx.measureText(t.trimEnd()).width > maxW) { lines.push(cur.trimEnd()); cur = w.trimStart(); } else cur = t; }
  if (cur.trim()) lines.push(cur.trimEnd());
  return lines;
};
// គូរអក្សរខ្មែរនីមួយៗជារូប PNG (ទទឹង = ទទឹងវីដេអូ) សម្រាប់ដាក់ក្នុង Export ដោយមិនពឹង libass
async function renderSubs(segs, W, H) {
  try { await document.fonts.load("600 40px 'Noto Sans Khmer'"); } catch { /* ប្រើ font ប្រព័ន្ធ */ }
  const fs = Math.round(Math.min(W, H) * 0.05), bandH = Math.round(H * 0.28), mb = Math.round(H * 0.07), lh = Math.round(fs * 1.45);
  const cv = document.createElement("canvas"); cv.width = W; cv.height = bandH; const ctx = cv.getContext("2d");
  const draw = (text) => {
    ctx.clearRect(0, 0, W, bandH); if (!text) return cv.toDataURL("image/png");
    ctx.font = `600 ${fs}px 'Noto Sans Khmer','Noto Sans SC',sans-serif`; ctx.textAlign = "center"; ctx.lineJoin = "round";
    const lines = wrapText(ctx, text, W * 0.9); let y = bandH - mb - (lines.length - 1) * lh;
    ctx.lineWidth = fs * 0.2; ctx.strokeStyle = "#000"; ctx.fillStyle = "#fff";
    for (const l of lines) { ctx.strokeText(l, W / 2, y); ctx.fillText(l, W / 2, y); y += lh; }
    return cv.toDataURL("image/png");
  };
  return { blank: draw(""), pngs: segs.map((s) => (s.km ? draw(s.km) : "")) };
}
const DEF_CHAR = "男主";
const ts = (sec) => { const ms = Math.round(Math.max(0, sec) * 1000), p = (n, w = 2) => String(n).padStart(w, "0"); return `${p(Math.floor(ms / 3600000))}:${p(Math.floor(ms / 60000) % 60)}:${p(Math.floor(ms / 1000) % 60)},${p(ms % 1000, 3)}`; };
const toSrt = (rows, key) => rows.map((s, i) => `${i + 1}\n${ts(s.start)} --> ${ts(s.end)}\n${s[key] || ""}\n`).join("\n");
const parseSrt = (txt) => {
  const T = /(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)/, sec = (h, m, s, ms) => +h * 3600 + +m * 60 + +s + +ms.padEnd(3, "0").slice(0, 3) / 1000;
  return txt.replace(/^\uFEFF/, "").replace(/\r\n?/g, "\n").split(/\n{2,}/).map((b) => {
    const lines = b.split("\n"), k = lines.findIndex((l) => T.test(l)); if (k < 0) return null;
    const m = lines[k].match(T); return { start: sec(m[1], m[2], m[3], m[4]), end: sec(m[5], m[6], m[7], m[8]), text: lines.slice(k + 1).join("\n").trim() };
  }).filter(Boolean);
};
// ក្រុមប៊ូតុង Export / Import សម្រាប់ដំណាក់កាលនីមួយៗ
function IOGroup({ label, color, formats, disabled, busy, accept, multiple, onExport, onImport }) {
  const [f, setF] = useState(formats[0][0]);
  return (
    <div className="flex items-center gap-1.5 rounded-xl px-2 py-1 text-xs" style={{ background: `${color}22`, border: `1px solid ${color}66` }}>
      <b style={{ color }}>{label}</b>
      <select className="ghost !py-0.5 !px-1 text-xs" value={f} onChange={(e) => setF(e.target.value)}>{formats.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
      <button className="btn text-xs !py-0.5 disabled:opacity-40" style={{ background: color, color: "#1a0b2e" }} disabled={disabled || !!busy} onClick={() => onExport(f)}>⬇ Export</button>
      <label className={`btn ghost text-xs !py-0.5 cursor-pointer ${busy ? "opacity-40 pointer-events-none" : ""}`}>⬆ Import<input type="file" hidden accept={accept} multiple={multiple} onChange={(e) => { const fs = [...e.target.files]; e.target.value = ""; if (fs.length) onImport(fs); }} /></label>
    </div>);
}
const voiceOf = (c) => c || "旁白";
const summarize = (rows) => {   // "👩 ស្រី 12 · 👨 ប្រុស 9 · 📖 អ្នកនិទាន 4"
  const n = {};
  rows.forEach((s) => { if (s.char) n[s.char] = (n[s.char] || 0) + 1; });
  return CHARS.filter(([k]) => n[k]).map(([k, l]) => `${l} ${n[k]}`).join(" · ");
};   // backend បម្លែងតួអង្គ → voice + rate + pitch

export default function App() {
  const [video, setVideo] = useState(null);           // {id,url}
  const [segs, setSegs] = useState([]);               // {id,start,end,zh,km,char,status,audio}
  const [sel, setSel] = useState(new Set());
  const [t, setT] = useState(0);
  const [dur, setDur] = useState(60);
  const [zoom, setZoom] = useState(20);               // px ក្នុង ១ វិនាទី
  const [busy, setBusy] = useState("");
  const [castMsg, setCastMsg] = useState("");   // សារសង្ខេបពី auto-scan តួអង្គ
  const [showSet, setShowSet] = useState(false);
  const [exported, setExported] = useState(false);
  const [showSub, setShowSub] = useState(true);       // បង្ហាញ/បិទ អក្សរលើវីដេអូ (និង Export)
  const [ar, setAr] = useState(9 / 16);
  const [vs, setVs] = useState({ w: 1080, h: 1920 });   // ទំហំវីដេអូពិត (px)                // aspect ratio ពិតរបស់វីដេអូ
  const [bgm, setBgm] = useState("");
  const [layers, setLayers] = useState(initLayers);   // 🏷️ Logo ⭐ Sponsor 🖼️ Overlay ©️ Khmer Text
  const [blurBoxes, setBlurBoxes] = useState([]);      // 🔲 Blur (ក្នុង pass តែមួយជាមួយ layer)
  const [tier, setTier] = useState("standard");        // standard | premium
  useEffect(() => { api("/api/settings").then((s) => setTier(s.tier || "standard")).catch(() => {}); }, [showSet]);
  const switchTier = async (k) => { const prev = tier; setTier(k); try { await api("/api/settings", { tier: k }); } catch (e) { setTier(prev); alert(e.message); } };
  const vref = useRef(); const played = useRef(null);

  // វីដេអូថ្មី → លុប file layer ចាស់ និង blur box ចាស់ (រក្សាទីតាំង/ទំហំដែលបានកំណត់)
  useEffect(() => {
    setLayers((s) => resetLayers(s));
    setBlurBoxes([]);
  }, [video?.id]);

  const patch = (id, p) => setSegs((s) => s.map((x) => (x.id === id ? { ...x, ...p } : x)));
  const run = (label, fn) => async () => { setBusy(label); try { await fn(); window.khOk && window.khOk(label); } catch (e) { alert(e.message); } setBusy(""); };

  // Sync វីដេអូ ↔ Subtitle ↔ សំឡេង
  const onTime = () => {
    const now = vref.current.currentTime; setT(now);
    const a = segs.find((s) => now >= s.start && now < s.end);
    if (a?.audio && played.current !== a.id) { played.current = a.id; new Audio(a.audio).play().catch((e) => console.error("Khmer audio failed:", a.audio, e)); }
    if (!a) played.current = null;
  };
  const active = segs.find((s) => t >= s.start && t < s.end);

  const onFile = async (f) => {
    if (!f) return; setBusy("កំពុង Upload...");
    try {
      const fd = new FormData(); fd.append("file", f);
      const v = await api("/api/upload", fd, true); setVideo(v);
      setBusy("កំពុងទាញអត្ថបទចិន (STT)...");
      const r = await api("/api/transcribe", { id: v.id });   // រួមទាំង auto-scan តួអង្គ
      const scanned = r.filter((s) => s.char).length;
      setSegs(r.map((s, i) => ({ ...s, id: i + 1, km: "", char: s.char || "旁白", conf: s.conf, status: "Pending", audio: "" })));
      if (scanned) setTimeout(() => setCastMsg(`✨ Auto-scan តួអង្គ ${scanned} បន្ទាត់ · ${summarize(r)}`), 50);
    } catch (e) { alert(e.message); }
    setBusy("");
  };

  // ---- Export / Import: STT · Translate · TTS ----
  const runWith = (label, fn) => async (...x) => { setBusy(label); try { await fn(...x); window.khOk && window.khOk(label); } catch (e) { alert(e.message); } setBusy(""); };
  const base = video?.id || "project";
  const save = (name, data, type = "text/plain") => { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([data], { type: type + ";charset=utf-8" })); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000); };
  const exportText = (key, fmt) => {   // key: "zh" (STT) | "km" (Translate) — រក្សាគ្រប់ segment ដើម្បីឱ្យ Import ត្រឡប់មកត្រូវលំដាប់
    if (fmt === "srt") save(`${base}_${key}.srt`, toSrt(segs, key), "application/x-subrip");
    else if (fmt === "txt") save(`${base}_${key}.txt`, segs.map((s) => (s[key] || "").replace(/\n/g, " ")).join("\n"));
    else save(`${base}_${key}.json`, JSON.stringify(segs.map(({ start, end, zh, km, char }) => ({ start, end, zh, km, char })), null, 2), "application/json");
  };
  const readItems = async (f, field) => {   // → [{start?,end?,text,char?}]
    const txt = await f.text();
    if (/\.json$/i.test(f.name)) { const j = JSON.parse(txt), arr = Array.isArray(j) ? j : j.segments || []; return arr.map((x) => (typeof x === "string" ? { text: x } : { start: +x.start || 0, end: +x.end || 0, text: x[field] ?? x.text ?? "", char: x.char })); }
    if (/\.srt$/i.test(f.name)) return parseSrt(txt);
    const items = txt.replace(/^\uFEFF/, "").split(/\r?\n/).map((l) => ({ text: l }));   // TXT: មួយបន្ទាត់ = មួយ segment
    while (items.length && !items[items.length - 1].text.trim()) items.pop(); return items;
  };
  const importStt = runWith("កំពុង Import STT...", async ([f]) => {
    const items = await readItems(f, "zh");
    if (!items.length || items[0].start === undefined) throw new Error("STT ត្រូវមានពេលវេលា — ប្រើ .srt ឬ .json");
    if (segs.length && !confirm("Import STT នឹងជំនួសអត្ថបទទាំងអស់ ហើយលុបការបកប្រែ និងសំឡេង។ បន្ត?")) return;
    setSegs(items.map((x, i) => ({ id: i + 1, start: x.start, end: x.end, zh: x.text, km: "", char: x.char || DEF_CHAR, status: "Pending", audio: "" })));
  });
  const importTr = runWith("កំពុង Import ការបកប្រែ...", async ([f]) => {
    const items = await readItems(f, "km"); if (!items.length) throw new Error("គ្មានទិន្នន័យក្នុង file");
    if (!segs.length) {
      if (items[0].start === undefined) throw new Error("សូម Transcribe ឬ Import STT ជាមុន (TXT គ្មានពេលវេលា)");
      return setSegs(items.map((x, i) => ({ id: i + 1, start: x.start, end: x.end, zh: "", km: x.text, char: x.char || DEF_CHAR, status: "Pending", audio: "" })));
    }
    const byTime = items[0].start !== undefined && items.length !== segs.length;   // ចំនួនមិនស្មើ → ផ្គូផ្គងតាមពេលវេលា
    if (!byTime && items.length !== segs.length) alert(`ចំនួនបន្ទាត់ (${items.length}) មិនស្មើ segments (${segs.length}) — ផ្គូផ្គងតាមលំដាប់`);
    setSegs((cur) => cur.map((s, i) => {
      const it = byTime ? items.filter((x) => Math.abs(x.start - s.start) <= 1.5).sort((x, y) => Math.abs(x.start - s.start) - Math.abs(y.start - s.start))[0] : items[i];
      return it ? { ...s, km: it.text, char: it.char || s.char, status: "Pending", audio: "" } : s;
    }));
  });
  const exportTts = runWith("កំពុង Export TTS...", async (kind) => {
    const r = await api("/api/tts_export", { kind, segments: segs.map((s, i) => ({ ...s, n: i + 1 })).filter((s) => s.audio), bgm });
    const a = document.createElement("a"); a.href = r.url; a.download = ""; a.click();
  });
  const importTts = runWith("កំពុង Import សំឡេង...", async (files) => {
    if (!segs.length) throw new Error("សូម Transcribe ឬ Import STT ជាមុន");
    const fd = new FormData(); files.forEach((f) => fd.append("files", f));
    const r = await api("/api/tts_import", fd, true), m = new Map(r.map((x) => [x.index, x.url]));
    setSegs((cur) => cur.map((s, i) => (m.has(i + 1) ? { ...s, audio: m.get(i + 1), status: "Done" } : s)));
    if (r.length !== segs.length) alert(`Import សំឡេង ${r.length} / ${segs.length} segments (លេខនៅដើមឈ្មោះ file = លំដាប់ segment)`);
  });

  // Auto-scan តួអង្គ (ឥតគិតថ្លៃ) — រក្សាការកែដោយដៃ
  const scanChars = runWith("កំពុងស្កេនតួអង្គ...", async () => {
    if (!segs.length) throw new Error("សូម Transcribe ឬ Import STT ជាមុន");
    const r = await api("/api/cast", { lines: segs.map((s) => s.zh || ""), keep: segs.map((s) => (s.manualChar ? s.char : "")) });
    setSegs((cur) => cur.map((x, i) => ({ ...x, char: r.items[i]?.char || x.char, conf: r.items[i]?.conf })));
    setCastMsg(`✨ រកឃើញតួអង្គ · ${r.summary}`);
  });

  const translate = run("កំពុងបកប្រែ...", async () => {
    const r = await api("/api/translate", { lines: segs.map((s) => s.zh) });
    setSegs((s) => s.map((x, i) => ({ ...x, km: r[i]?.km ?? x.km, char: r[i]?.char ?? x.char })));
  });
  const genAudio = run("កំពុងបង្កើតសំឡេង...", async () => {
    let failed = 0;
    for (const s of segs) {
      if (!s.km) continue; patch(s.id, { status: "Generating" });
      let ok = false;
      for (let t = 0; t < 3 && !ok; t++) {
        try { const r = await api("/api/tts", { text: s.km, char: voiceOf(s.char), speed: 0 }); patch(s.id, { audio: r.url, status: "Done" }); ok = true; }
        catch (e) { console.error("TTS failed:", s.km, e); await new Promise((res) => setTimeout(res, 1000 * (t + 1))); }
      }
      if (!ok) { patch(s.id, { status: "Error" }); failed++; }
    }
    if (failed) throw new Error("បង្កើតសំឡេងមិនបាន " + failed + " ឃ្លា (មើលស្ថានភាព Error ក្នុងតារាង)");
  });
  const [showExp, setShowExp] = useState(false);
  const [expQ, setExpQ] = useState("hd");
  const [expFast, setExpFast] = useState(true);      // ⚡ លឿនបំផុត (veryfast + crf ខ្ពស់បន្តិច)
  const [expProg, setExpProg] = useState(null);      // {percent, eta, speed, state}
  const [encInfo, setEncInfo] = useState(null);      // {encoder, hardware, label}
  useEffect(() => { if (showExp) api("/api/encoder").then(setEncInfo).catch(() => {}); }, [showExp]);
  const saveRef = useRef(null);
  const [saveName, setSaveName] = useState("");
  const pickSave = async () => {
    if (!window.showSaveFilePicker) { alert("Browser នេះមិនគាំទ្រការជ្រើសកន្លែងរក្សាទុកទេ (ប្រើ Chrome ឬ Edge)។ file នឹងទៅ Downloads។"); return; }
    try {
      const h = await window.showSaveFilePicker({ suggestedName: "video_km.mp4", types: [{ description: "MP4 video", accept: { "video/mp4": [".mp4"] } }] });
      saveRef.current = h; setSaveName(h.name);
    } catch (e) { /* បោះបង់ */ }
  };
  const saveOut = async (url) => {
    const h = saveRef.current; saveRef.current = null; setSaveName("");
    if (h) {
      try { const blob = await (await fetch(url)).blob(); const w = await h.createWritable(); await w.write(blob); await w.close(); return; }
      catch (e) { console.error("Save failed:", e); }
    }
    const a = document.createElement("a"); a.href = url; a.download = "video_km.mp4"; document.body.appendChild(a); a.click(); a.remove();
  };
  const expDialog = showExp ? createPortal(
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setShowExp(false)}>
      <div className="glass bg-[#1a1245]/95 p-5 w-[440px] space-y-3" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold">Export Video</h2>
        <div className="text-sm font-semibold">គុណភាព</div>
        {[["hd", "ច្បាស់ (HD 1080p)", "Upscale ទៅ 1080p ស្វ័យប្រវត្តិ · គុណភាពខ្ពស់ · យឺតជាង · file ធំជាង"], ["normal", "ធម្មតា", "ទំហំដើម · លឿន · file តូច"]].map(([v, t, d]) => (
          <label key={v} className="glass p-3 flex gap-2 items-start cursor-pointer" style={{ borderLeft: `4px solid ${expQ === v ? "#a78bfa" : "transparent"}` }}>
            <input type="radio" name="expq" checked={expQ === v} onChange={() => setExpQ(v)} />
            <span><span className="block text-sm font-semibold">{t}</span><span className="block text-xs opacity-70">{d}</span></span>
          </label>))}
        <div className="text-sm font-semibold flex items-center gap-2">ល្បឿន
          {encInfo && <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: encInfo.hardware ? "#34d39933" : "#ffffff14", color: encInfo.hardware ? "#6ee7b7" : "#ffffff88" }}>{encInfo.label}</span>}
        </div>
        <label className="glass p-3 flex gap-2 items-start cursor-pointer" style={{ borderLeft: `4px solid ${expFast ? "#34d399" : "transparent"}` }}>
          <input type="checkbox" checked={expFast} onChange={(e) => setExpFast(e.target.checked)} style={{ accentColor: "#34d399" }} />
          <span><span className="block text-sm font-semibold">⚡ លឿនបំផុត (ណែនាំ)</span>
            <span className="block text-xs opacity-70">ប្រើ encoder របស់ GPU បើមាន · preset លឿន · គុណភាពខុសគ្នាតិចតួច</span></span>
        </label>
        <div className="text-sm font-semibold">បញ្ចូលក្នុង Export (pass តែមួយ)</div>
        <div className="glass p-2 text-xs space-y-0.5">
          {[
            [showSub && segs.some((s) => s.km), `💬 អក្សរខ្មែរ (${segs.filter((s) => s.km).length} បន្ទាត់)`],
            [segs.some((s) => s.audio), `🎙️ សំឡេងខ្មែរ (${segs.filter((s) => s.audio).length} ឃ្លា)`],
            [!!bgm, "🎵 BGM (ducking)"],
            ...LAYERS.filter((L) => layers[L.k].on).map((L) => [true, L.label]),
            [blurBoxes.length > 0, `🔲 Blur (${blurBoxes.length} box)`],
          ].map(([on, label]) => (
            <div key={label} style={{ color: on ? "#a7f3d0" : "#ffffff55" }}>{on ? "✅" : "⬜"} {label}</div>
          ))}
        </div>
        <div className="text-sm font-semibold">កន្លែងរក្សាទុក</div>
        <div className="flex gap-2 items-center"><button className="ghost" onClick={pickSave}>📁 Browse...</button><span className="text-xs opacity-70 truncate">{saveName || "មិនទាន់ជ្រើស (ទៅ Downloads)"}</span></div>
        <div className="flex gap-2 justify-end"><button className="ghost" onClick={() => setShowExp(false)}>បោះបង់</button><button className="neon" onClick={() => { setShowExp(false); exportV(); }}>Export</button></div>
      </div>
    </div>, document.body) : null;
  // ទទឹងវីដេអូពេល Export (HD = upscale ទៅ 1080p) → អក្សរខ្មែរគូរត្រូវទំហំពិត មិនព្រិល
  const outW = useMemo(() => {
    const w = vs.w || 1080, h = vs.h || 1920;
    if (expQ !== "hd") return w;
    const m = Math.min(w, h);
    return m >= 1080 ? w : Math.round(w * 1080 / m);
  }, [expQ, vs]);

  // Layer ដែលបើក → payload សម្រាប់ Export / Apply (Khmer Text → PNG គុណភាពពេញ)
  const layerPayload = useCallback(async () => {
    const out = [];
    for (const L of LAYERS) {
      const s = layers[L.k];
      if (!s.on) continue;
      const one = { kind: L.k, enabled: true, x: s.x, y: s.y, size: s.size, opacity: s.op };
      if (L.k === "text") {
        if (!s.text.trim()) continue;
        one.data = await renderTextPng(s.text, s.color, outW, s.size);
        if (!one.data) continue;
      } else {
        if (!s.url) continue;
        one.file = s.url;
      }
      out.push(one);
    }
    return out;
  }, [layers, outW]);

  const blurPayload = useCallback(() => blurBoxes.map(({ id, ...b }) => b), [blurBoxes]);

  // Apply ក្រោយ Export រួច: Layers + Blur ក្នុង pass តែមួយ
  const applyFx = runWith("កំពុងដាក់ Layers + Blur...", async () => {
    if (!video) throw new Error("សូម Upload វីដេអូជាមុន");
    const ly = await layerPayload(), bx = blurPayload();
    if (!ly.length && !bx.length) throw new Error("គ្មាន Layer ឬ Blur ដែលបានបើក");
    const r = await api("/api/finish", { id: video.id, layers: ly, boxes: bx });
    const a = document.createElement("a"); a.href = r.url; a.download = ""; a.click();
  });

  const exportV = run("កំពុង Export...", async () => {
    let pngs = [], blank = "";
    if (showSub) ({ pngs, blank } = await renderSubs(segs, vs.w, vs.h));
    const [ly, bx] = [await layerPayload(), blurPayload()];   // Logo/Sponsor/Overlay/Text + Blur ក្នុង Export តែមួយ
    const r = await api("/api/export", {
      id: video.id, segments: segs.map((s, i) => ({ ...s, png: pngs[i] || "" })),
      subs: showSub, blank, bgm, quality: expQ, speed: expFast ? "fast" : "",
      layers: ly, boxes: bx,
    });
    if (r.url) { setExported(true); return saveOut(r.url); }   // server ចាស់ → sync
    setExpProg({ percent: 0, eta: 0, state: "running" });
    try {
      for (;;) {   // poll progress ពិតពី FFmpeg
        await new Promise((ok) => setTimeout(ok, 700));
        const j = await api(`/api/export_status?id=${encodeURIComponent(video.id)}`);
        if (j.state === "done") { setExpProg({ percent: 100, eta: 0, state: "done" }); setExported(true); await saveOut(j.url); break; }
        if (j.state === "error") throw new Error(j.error || "Export បរាជ័យ");
        if (j.state === "none") throw new Error("Job បាត់ (server restart?) សូមព្យាយាមម្តងទៀត");
        setExpProg(j);
      }
    } finally { setTimeout(() => setExpProg(null), 1500); }
  });

  // Progress ពិត (ពី FFmpeg) — បង្ហាញ % និង ETA ជំនួសការរង់ចាំទទេ
  const mmss = (s) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;
  const expProgUI = expProg ? createPortal(
    <div style={{ position: "fixed", left: "50%", transform: "translateX(-50%)", bottom: 28, zIndex: 60, width: 360 }}
      className="glass bg-[#1a1245]/95 p-3 rounded-xl">
      <div className="flex items-center justify-between text-xs mb-1.5">
        <b>{expProg.state === "done" ? "✅ Export ចប់" : "🎬 កំពុង Export…"}</b>
        <span style={{ color: "#a7f3d0" }}>{Math.round(expProg.percent || 0)}%</span>
      </div>
      <div style={{ height: 8, borderRadius: 99, background: "#ffffff22", overflow: "hidden" }}>
        <div style={{ width: `${Math.max(1.5, expProg.percent || 0)}%`, height: "100%", borderRadius: 99,
          background: "linear-gradient(90deg,#22d3ee,#34d399)", transition: "width .4s ease" }} />
      </div>
      <div className="flex justify-between text-xs opacity-70 mt-1">
        <span>{expProg.speed ? `${expProg.speed}× លឿនជាងពេលវេជ្ជមាន` : "កំពុងចាប់ផ្តើម…"}</span>
        <span>{expProg.eta > 1 ? `នៅសល់ ~${mmss(expProg.eta)}` : ""}</span>
      </div>
    </div>, document.body) : null;
  const [bgmVol, setBgmVol] = useState(0.5);
  const bgmAud = useRef(null);
  useEffect(() => {   // Preview BGM តាមវីដេអូ (play / pause / seek)
    const v = vref.current;
    if (!bgm || !v) return;
    const wasMuted = v.muted; v.muted = true;   // ឮតែ BGM
    const a = new Audio(bgm); a.loop = true; a.volume = bgmVol; bgmAud.current = a;
    const sync = () => { if (a.duration) a.currentTime = v.currentTime % a.duration; };
    const play = () => { sync(); a.play().catch(() => {}); };
    const pause = () => a.pause();
    v.addEventListener("play", play); v.addEventListener("pause", pause);
    v.addEventListener("seeked", sync); v.addEventListener("ended", pause);
    if (!v.paused) play();
    return () => {
      v.removeEventListener("play", play); v.removeEventListener("pause", pause);
      v.removeEventListener("seeked", sync); v.removeEventListener("ended", pause);
      a.pause(); bgmAud.current = null; v.muted = wasMuted;
    };
  }, [bgm, video]);
  useEffect(() => { if (bgmAud.current) bgmAud.current.volume = bgmVol; }, [bgmVol]);
  const uploadBgm = runWith("កំពុង Upload BGM...", async (f) => {
    const fd = new FormData(); fd.append("file", f);
    const r = await api("/api/bgm?id=" + video.id, fd, true);
    if (r && r.warning) alert(r.warning);
    if (r.url) { setBgm(r.url + "?v=" + Date.now()); return; }
    for (;;) {   // រង់ចាំ Demucs ដកសំដី (background job)
      await new Promise((ok) => setTimeout(ok, 700));
      const j = await api("/api/bgm_status?id=" + video.id);
      if (j.state === "done") { setBgm(j.url + "?v=" + Date.now()); return; }
      if (j.state === "error") throw new Error(j.error || "BGM បរាជ័យ");
      if (j.state === "none") throw new Error("Job បាត់ (server restart?) សូម upload ម្តងទៀត");
    }
  });
  const findReplace = () => { const a = prompt("ស្វែងរក:"); if (!a) return; const b = prompt("ជំនួសដោយ:") ?? ""; setSegs((s) => s.map((x) => ({ ...x, km: x.km.split(a).join(b) }))); };
  const addText = () => setSegs((s) => [...s, { id: Date.now(), start: t, end: t + 2, zh: "", km: "", char: "男主", status: "Pending", audio: "" }].sort((a, b) => a.start - b.start));
  const del = () => { setSegs((s) => s.filter((x) => !sel.has(x.id))); setSel(new Set()); };

  const B = ({ children, c = "violet", ...p }) => <button className={`btn b-${c} text-sm disabled:opacity-40`} disabled={!!busy} {...p}>{children}</button>;

  return (
    <div className="h-screen flex flex-col">
      <header className="flex items-center gap-4 px-4 pt-3">
        <div className="flex items-center gap-2"><span className="logo" /><b className="text-lg" style={{ fontFamily: "'Bricolage Grotesque','Noto Sans Khmer',sans-serif" }}>KH Drama Studio</b></div>
        <nav className="flex gap-1.5 mx-auto">{[["Upload", !!video], ["Transcribe", segs.length > 0], ["Translate", segs.some((s) => s.km)], ["Voice", segs.some((s) => s.audio)], ["Export", exported]].map(([l, on], i) => <span key={l} className={`step ${on ? "on" : ""}`} style={{ "--c": STEP_C[i] }}>{i + 1}. {l}</span>)}</nav>
        <div className="flex rounded-[10px] overflow-hidden border border-purple-400/30 text-xs" title="កម្រិតគុណភាព">
            {[["standard", "Standard"], ["premium", "★ Premium"]].map(([k, l]) => (
              <button key={k} disabled={!!busy} onClick={() => switchTier(k)}
                className={`px-3 py-1.5 disabled:opacity-40 ${tier === k ? (k === "premium" ? "bg-gradient-to-r from-amber-500 to-pink-500 text-black font-semibold" : "bg-indigo-500") : "hover:bg-purple-600/20"}`}>{l}</button>))}
          </div>
          <button className="ghost" onClick={() => setShowSet(true)}>⚙ Settings</button>
      </header>
    <div className="flex-1 min-h-0 grid grid-rows-[1fr_240px] gap-3 p-3" style={{ gridTemplateColumns: `clamp(240px, calc((100vh - 230px) * ${ar} + 24px), 520px) minmax(0, 1fr)` }}>
      {/* ១. Video Preview */}
      <section className="pnl pnl-pink row-span-2 p-3 pt-4 flex flex-col gap-2 min-h-0 overflow-y-auto">
        {video ? <div className="relative mx-auto bg-black rounded-xl overflow-hidden shrink-0" style={{ aspectRatio: ar, width: `min(100%, calc((100vh - 230px) * ${ar}))`, containerType: "inline-size" }}>
          <video ref={vref} src={video.url} className="w-full h-full object-cover" onTimeUpdate={onTime} muted
            onLoadedMetadata={(e) => { setDur(e.target.duration); if (e.target.videoWidth) { setAr(e.target.videoWidth / e.target.videoHeight); setVs({ w: e.target.videoWidth, h: e.target.videoHeight }); } }} />
          {showSub && active?.km && <div className="absolute bottom-[7%] inset-x-[4%] text-center font-semibold leading-snug [text-shadow:0_0_6px_#000,0_0_6px_#000,0_0_3px_#000]" style={{ fontSize: "clamp(12px,5cqw,30px)" }}>{active.km}</div>}
        </div>
        : <div className="flex-1 min-h-[200px] bg-black/60 rounded-xl flex items-center justify-center"><label className="ghost cursor-pointer">ជ្រើសវីដេអូ<input type="file" accept="video/*" hidden onChange={(e) => onFile(e.target.files[0])} /></label></div>}
        <div className="flex items-center gap-2 text-sm">
          <button className="ghost" onClick={() => vref.current?.paused ? vref.current.play() : vref.current.pause()}>▶/⏸</button>
          <input type="range" className="flex-1" min={0} max={dur} step={0.1} value={t} onChange={(e) => { vref.current.currentTime = +e.target.value; }} />
          <span>{tc(t)}</span>
        </div>
        <div className="flex items-center gap-2 text-sm">🔊<input type="range" className="flex-1" min={0} max={1} step={0.05} defaultValue={1} onChange={(e) => (vref.current.volume = +e.target.value)} /></div>
        <button className={`btn text-sm ${showSub ? "b-cyan" : "ghost"}`} aria-pressed={showSub} onClick={() => setShowSub((v) => !v)}>💬 Subtitles: {showSub ? "On" : "Off"}</button>
      </section>

      {/* ២. Subtitle Editor */}
      <section className="pnl pnl-violet p-3 pt-4 flex flex-col min-h-0 min-w-0">
        <div className="flex gap-2 mb-2 flex-wrap items-center">
          <B c="violet" onClick={addText}>+ Add Text</B><B c="red" onClick={del}>Delete</B><B c="amber" onClick={findReplace}>Find &amp; Replace</B><B c="pink" onClick={scanChars}>🔍 Scan Characters (ឥតគិតថ្លៃ)</B>
          <span className="text-xs opacity-70">{busy}</span>
          {castMsg && <span className="text-xs" style={{ color: "#6ee7b7" }}>{castMsg}</span>}

        </div>
        <div className="flex flex-wrap gap-2 mb-2">
          <IOGroup label="STT" color="#fb923c" formats={[["srt", "SRT"], ["txt", "TXT"], ["json", "JSON"]]} accept=".srt,.json" disabled={!segs.length} busy={busy} onExport={(f) => exportText("zh", f)} onImport={importStt} />
          <IOGroup label="Translate" color="#fbbf24" formats={[["srt", "SRT"], ["txt", "TXT"], ["json", "JSON"]]} accept=".srt,.txt,.json" disabled={!segs.some((s) => s.km)} busy={busy} onExport={(f) => exportText("km", f)} onImport={importTr} />
          <IOGroup label="TTS" color="#34d399" formats={[["mp3", "MP3 track"], ["zip", "ZIP clips"]]} accept=".zip,.mp3,.wav,.m4a,.ogg,.aac,.flac,audio/*" multiple disabled={!segs.some((s) => s.audio)} busy={busy} onExport={exportTts} onImport={importTts} />
          <>
            <label className="btn btn-block text-sm cursor-pointer" style={{ background: "#fbbf24", color: "#000" }}>
              🎵 {bgm ? "Change BGM" : "Upload BGM"}
              <input type="file" hidden accept="audio/*,video/*,.mp3,.wav,.m4a,.ogg,.aac,.flac,.mp4,.mov,.mkv,.webm" disabled={!video} onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) uploadBgm(f); }} />
            </label>
            {bgm && <button className="btn ghost text-xs" onClick={() => setBgm("")}>✕ Remove BGM</button>}
            {bgm && <label className="flex items-center gap-2 text-xs">🔊 BGM<input type="range" min="0" max="1" step="0.05" value={bgmVol} onChange={(e) => setBgmVol(+e.target.value)} className="flex-1" /></label>}
          </>
          <OverlayPanel video={video} layers={layers} setLayers={setLayers} boxes={blurBoxes} setBoxes={setBlurBoxes} onApply={applyFx} />
        </div>
        <div className="overflow-auto flex-1 text-sm">
          <table className="w-full table-fixed"><colgroup>{[30, 34, 62, 62, null, null, 100, 84].map((w, i) => <col key={i} style={w ? { width: w } : undefined} />)}</colgroup>
            <thead className="sticky top-0 bg-[#1a1450] text-left"><tr>{["", "#", "Start", "End", "中文", "ខ្មែរ", "Character", "Voice"].map((h) => <th key={h} className="p-1">{h}</th>)}</tr></thead>
            <tbody>{segs.map((s, i) => (
              <tr key={s.id} className={`border-t border-white/10 align-top ${s === active ? "row-on" : ""}`}>
                <td><input type="checkbox" checked={sel.has(s.id)} onChange={() => setSel((o) => { const n = new Set(o); n.has(s.id) ? n.delete(s.id) : n.add(s.id); return n; })} /></td>
                <td>{i + 1}</td>
                <td><input className="w-14" value={s.start.toFixed(1)} onChange={(e) => patch(s.id, { start: +e.target.value || 0 })} /></td>
                <td><input className="w-14" value={s.end.toFixed(1)} onChange={(e) => patch(s.id, { end: +e.target.value || 0 })} /></td>
                <td><textarea rows={2} className="w-full resize-none leading-snug" value={s.zh} onChange={(e) => patch(s.id, { zh: e.target.value })} /></td>
                <td><textarea rows={2} className="w-full resize-none leading-snug" value={s.km} onChange={(e) => patch(s.id, { km: e.target.value, status: "Pending", audio: "" })} /></td>
                <td className="whitespace-nowrap">
                  <i className="dot" style={{ background: CC(s.char) }} title={s.conf ? `ជឿជាក់ ${Math.round(s.conf * 100)}%` : ""} />
                  <select className="w-[104px] rounded px-1 py-0.5 text-xs" value={CHAR_LABEL[s.char] ? s.char : "旁白"}
                    title={s.conf ? `Auto-scan ជឿជាក់ ${Math.round(s.conf * 100)}% · អាចកែបាន` : "ជ្រើសតួអង្គ"}
                    style={{ background: "#1a1245", border: `1px solid ${CC(s.char)}88`, color: "#fff" }}
                    onChange={(e) => patch(s.id, { char: e.target.value, manualChar: true })}>
                    {CHARS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                  </select>
                </td>
                <td><span className={`chip chip-${s.status}`}>{s.status}</span></td>
              </tr>))}</tbody>
          </table>
          {!segs.length && <p className="opacity-60 p-4">Upload វីដេអូ ដើម្បីចាប់ផ្តើម។</p>}
        </div>
      </section>

      {/* ៣. Timeline */}
      <section className="pnl pnl-teal col-start-2 p-3 pt-4 flex flex-col gap-2 min-h-0 min-w-0">
        <div className="flex gap-2 items-center text-sm">
          <B c="cyan" onClick={translate}>Translate</B><B c="green" onClick={genAudio}>Generate Khmer Audio</B><B c="orange" onClick={() => setShowExp(true)}>Export Video</B>{expDialog}{expProgUI}
          <span className="ml-auto">Zoom</span><input type="range" min={5} max={80} value={zoom} onChange={(e) => setZoom(+e.target.value)} />
        </div>
        <Timeline {...{ bgm, segs, patch, dur, zoom, t, video, seek: (x) => { if (vref.current) vref.current.currentTime = x; } }} />
      </section>
      {showSet && <Settings tier={tier} onClose={() => setShowSet(false)} />}
    </div>
    </div>
  );
}

function Timeline({ bgm, segs, patch, dur, zoom, t, video, seek }) {
  const cv = useRef(); const W = Math.max(dur * zoom, 600);
  useEffect(() => {  // Waveform ពីសំឡេងវីដេអូ
    if (!bgm) { cv.current?.getContext("2d").clearRect(0, 0, W, 50); return; } let dead = false;
    (async () => {
      const buf = await (await fetch(bgm, { cache: "reload" })).arrayBuffer();
      const a = await new AudioContext().decodeAudioData(buf).catch(() => null); if (!a || dead) return;
      const d = a.getChannelData(0), c = cv.current.getContext("2d"), step = Math.floor(d.length / W) || 1;
      c.clearRect(0, 0, W, 50); const g = c.createLinearGradient(0, 0, W, 0); g.addColorStop(0, "#22d3ee"); g.addColorStop(.5, "#a78bfa"); g.addColorStop(1, "#f472b6"); c.fillStyle = g;
      for (let x = 0; x < W; x++) { let m = 0; for (let j = 0; j < step; j += 40) m = Math.max(m, Math.abs(d[x * step + j] || 0)); c.fillRect(x, 25 - m * 25, 1, m * 50); }
    })();
    return () => { dead = true; };
  }, [bgm, W]);
  const drag = useCallback((e, s, mode) => {   // អូសទម្លាក់ពេលវេលា
    e.stopPropagation(); const x0 = e.clientX, { start, end } = s;
    const mv = (m) => { const d = (m.clientX - x0) / zoom;
      if (mode === "move") patch(s.id, { start: Math.max(0, start + d), end: end + d });
      else patch(s.id, { end: Math.max(start + 0.2, end + d) }); };
    const up = () => { removeEventListener("pointermove", mv); removeEventListener("pointerup", up); };
    addEventListener("pointermove", mv); addEventListener("pointerup", up);
  }, [zoom, patch]);
  const Track = ({ label, children, h = 50, c }) => <div className="flex"><div className="w-14 text-xs font-semibold shrink-0" style={{ color: c }}>{label}</div><div className="relative" style={{ width: W, height: h }}>{children}</div></div>;
  const Blk = ({ s, voice, txt }) => <div onPointerDown={(e) => drag(e, s, "move")} className="absolute top-1 h-[85%] rounded-md px-1 text-xs truncate cursor-grab font-semibold" style={{ left: s.start * zoom, width: (s.end - s.start) * zoom, background: voice ? CC(s.char) : `linear-gradient(135deg,${CC(s.char)}d9,${CC(s.char)}55)`, color: voice ? "#1a0b2e" : "#fff" }}>{txt}<i onPointerDown={(e) => drag(e, s, "resize")} className="absolute right-0 top-0 h-full w-2 cursor-ew-resize bg-white/30" /></div>;
  return (
    <div className="overflow-auto flex-1" onClick={(e) => seek((e.clientX - e.currentTarget.getBoundingClientRect().left + e.currentTarget.scrollLeft - 56) / zoom)}>
      <div className="relative flex flex-col gap-1">
        <div className="absolute top-0 bottom-0 w-0.5 bg-yellow-300 shadow-[0_0_8px_#fde047] z-10" style={{ left: 56 + t * zoom }} />
        <Track label="TEXT" c="#22d3ee">{segs.map((s) => <Blk key={s.id} s={s} txt={s.km || s.zh} />)}</Track>
        <Track label="VOICE" c="#34d399">{segs.filter((s) => s.audio).map((s) => <Blk key={s.id} s={s} voice txt={s.char} />)}</Track>
        <Track label="BGM" c="#fbbf24"><canvas ref={cv} width={W} height={50} /></Track>
      </div>
    </div>
  );
}

function Settings({ onClose, tier }) {
  const [d, setD] = useState({}); const [cat, setCat] = useState(null); const [tiers, setTiers] = useState(null); const [et, setEt] = useState(tier);
  useEffect(() => { api("/api/settings").then(setD); api("/api/catalog").then(setCat); api("/api/tiers").then((r) => setTiers(r.tiers)); }, []);
  if (!cat || !tiers) return null;
  const inp = (k, label, ph, type = "text") => <label className="block text-xs mt-2">{label}<input type={type} placeholder={ph} className="w-full ghost mt-1 text-sm" value={d[k] || ""} onChange={(e) => setD({ ...d, [k]: e.target.value })} /></label>;
  const roles = [["translate", "សេវាបកប្រែ (ចិន→ខ្មែរ)"], ["stt", "ទាញអត្ថបទចិនពីសំឡេង (STT)"], ["tts", "សំឡេងខ្មែរ (TTS)"]];
  const save = async () => { await api("/api/settings", d); onClose(); };
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="glass bg-[#1a1245]/95 p-5 w-[520px] max-h-[90vh] overflow-auto space-y-3" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold">Settings</h2>
        <div className="flex gap-2 text-sm">
          {Object.keys(tiers).map((k) => <button key={k} onClick={() => setEt(k)} className={et === k ? "neon" : "ghost"}>{k === "premium" ? "★ Premium" : "Standard"}</button>)}
          <span className="text-xs opacity-60 self-center ml-auto">{et === tier ? "កំពុងប្រើ" : "កំពុងកែ (មិនទាន់ប្រើ)"} · API Key ប្រើរួមគ្នា</span>
        </div>
        {roles.map(([r, title]) => {
          const pk = `${et}_${r}_provider`, tp = tiers[et][r].provider;
          const p = d[pk] || (et === "standard" && d[r + "_provider"]) || tp, c = cat[r][p];
          const dm = tp === p && tiers[et][r].model ? tiers[et][r].model : c.model;
          return (
            <div key={r} className="glass p-3" style={{ borderLeft: `4px solid ${{ translate: "#22d3ee", stt: "#fbbf24", tts: "#34d399" }[r]}` }}>
              <div className="text-sm font-semibold">{title}</div>
              <select className="w-full ghost mt-2 text-sm" value={p} onChange={(e) => setD({ ...d, [pk]: e.target.value })}>{Object.keys(cat[r]).map((o) => <option key={o}>{o}</option>)}</select>
              {c.base && inp("base_" + r, "Base URL (OpenAI-compatible)", "https://.../v1")}
              {c.key && inp(p === "custom" ? `key_custom_${r}` : "key_" + p, "API Key", "ដាក់ Key នៅទីនេះ", "password")}
              {c.model !== undefined && (r === "stt" && p === "local"
                ? <label className="block text-xs mt-2">Model<select className="w-full ghost mt-1 text-sm" value={d[`${et}_${r}_model_${p}`] || dm} onChange={(e) => setD({ ...d, [`${et}_${r}_model_${p}`]: e.target.value })}>{[["tiny", "tiny (លឿន, RAM តិច)"], ["base", "base (ល្អជាង, RAM ច្រើនជាង)"], ["small", "small (ត្រូវការ RAM ≥ 1GB)"]].map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></label>
                : inp(`${et}_${r}_model_${p}`, "Model", dm))}
              {c.region && inp("azure_region", "Azure Region", "southeastasia")}
              {r === "tts" && <>{inp(`tts_male_${p}`, "សំឡេងប្រុស", c.male)}{inp(`tts_female_${p}`, "សំឡេងស្រី", c.female)}</>}
              {!c.key && <div className="text-xs opacity-60 mt-2">ឥតគិតថ្លៃ — មិនត្រូវការ Key</div>}
            </div>);
        })}
        <div className="flex gap-2 justify-end"><button className="ghost" onClick={onClose}>បោះបង់</button><button className="neon" onClick={save}>រក្សាទុក</button></div>
      </div>
    </div>
  );
}
