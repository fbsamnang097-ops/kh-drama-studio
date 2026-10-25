import { useCallback, useEffect, useMemo, useState } from "react";

/* 🎁 ជូនដំណឹងកំណែថ្មី — ពិនិត្យ GitHub Releases តាម backend (/api/update)
 *
 * ហេតុអ្វី៖ អ្នកប្រើដំឡើង app ហើយមិនដឹងថាមានកំណែថ្មី → ខកខានការកែកំហុស។
 * បដានេះបង្ហាញពេលមានកំណែថ្មី ជាមួយតំណទាញយកផ្ទាល់ (តាម OS)។
 */

const AUTO_MS = 6 * 60 * 60 * 1000;      // ពិនិត្យឡើងវិញរៀងរាល់ ៦ ម៉ោង
const FOCUS_MS = 30 * 60 * 1000;         // ពេលត្រឡប់មក app វិញ (មិនញឹកញាប់ជាង ៣០ នាទី)
const SKIP_KEY = "khUpdateSkip";         // "មិនរំលឹកកំណែនេះ"

export function useUpdate({ auto = true, delay = 2500 } = {}) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const check = useCallback(async (force = false) => {
    setBusy(true);
    setErr("");
    try {
      const r = await fetch(`/api/update${force ? "?refresh=1" : ""}`, { cache: "no-store" });
      const j = await r.json();
      setData(j);
      if (!j.ok && j.error) setErr(j.error);
      return j;
    } catch (e) {
      setErr(String((e && e.message) || e));
      return null;
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    if (!auto) return;
    const t = setTimeout(() => check(false), delay);
    return () => clearTimeout(t);
  }, [auto, check, delay]);

  useEffect(() => {
    if (!auto) return;
    const iv = setInterval(() => check(false), AUTO_MS);
    let last = Date.now();
    const onFocus = () => {
      if (Date.now() - last < FOCUS_MS) return;
      last = Date.now();
      check(false);
    };
    window.addEventListener("focus", onFocus);
    return () => { clearInterval(iv); window.removeEventListener("focus", onFocus); };
  }, [auto, check]);

  return { data, busy, err, check };
}

function osGuess() {
  try {
    const p = (navigator.userAgentData?.platform || navigator.platform || "").toLowerCase();
    if (/win/.test(p)) return "windows";
    if (/mac/.test(p)) return "mac_arm";
  } catch { /* ignore */ }
  return "windows";
}

function dismissKey() {
  try { return localStorage.getItem(SKIP_KEY) || ""; } catch { return ""; }
}

/** បដាធំ — បង្ហាញពេលមានកំណែថ្មី (អាចបិទបាន) */
export function UpdateBanner({ upd }) {
  const { data, busy, check } = upd || {};
  const [skip, setSkip] = useState(dismissKey);
  const [later, setLater] = useState(false);
  const [open, setOpen] = useState(false);

  const dl = useMemo(() => {
    if (!data || !data.downloads) return "";
    const key = osGuess();
    return data.downloads[key] || data.downloads.windows || data.url;
  }, [data]);

  if (!data || !data.available) return null;
  if (later || skip === data.latest) return null;

  const btn = "text-xs rounded-lg px-2.5 py-1 font-semibold";
  return (
    <div className="mx-3 mt-2 rounded-xl px-3 py-2"
      style={{ background: "linear-gradient(90deg,rgba(52,211,153,.20),rgba(34,211,238,.14))",
               border: "1px solid rgba(52,211,153,.55)" }}>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <b style={{ color: "#6ee7b7" }}>🎁 មានកំណែថ្មី v{data.latest}</b>
        <span className="text-xs opacity-70">អ្នកកំពុងប្រើ v{data.current}</span>
        <a href={dl || data.url} target="_blank" rel="noreferrer"
          className={btn} style={{ background: "#34d399", color: "#052e1b" }}>⬇ ទាញយក</a>
        <a href={data.url} target="_blank" rel="noreferrer"
          className={btn} style={{ background: "rgba(255,255,255,.12)", color: "#e9d5ff" }}>📄 ព័ត៌មានកំណែ</a>
        {data.notes && (
          <button className={btn} style={{ background: "rgba(255,255,255,.08)", color: "#c4b5fd" }}
            onClick={() => setOpen((v) => !v)}>{open ? "▴ បិទអ្វីថ្មី" : "▾ អ្វីថ្មី?"}</button>
        )}
        <span className="ml-auto flex gap-2">
          <button className={btn} style={{ background: "rgba(255,255,255,.10)", color: "#fff" }}
            onClick={() => setLater(true)}>ផ្សាយពេលក្រោយ</button>
          <button className={btn} style={{ background: "rgba(255,255,255,.06)", color: "#ffffff99" }}
            title={`លាក់ដំណឹង v${data.latest} រហូតដល់មានកំណែបន្ទាប់`}
            onClick={() => { try { localStorage.setItem(SKIP_KEY, data.latest); } catch { /* ignore */ } setSkip(data.latest); }}>
            មិនរំលឹក
          </button>
        </span>
        {busy && <span className="text-xs opacity-60">…</span>}
      </div>

      {open && data.notes && (
        <pre className="text-[11px] mt-2 p-2 rounded-lg whitespace-pre-wrap max-h-40 overflow-auto"
          style={{ background: "rgba(0,0,0,.28)", color: "#e5e7eb" }}>{data.notes}</pre>
      )}

      {(data.downloads?.mac_arm || data.downloads?.mac_intel || data.downloads?.windows) && (
        <div className="flex flex-wrap gap-3 text-[11px] mt-1.5 opacity-75">
          {data.downloads.windows && <a href={data.downloads.windows} target="_blank" rel="noreferrer">🪟 Windows .exe</a>}
          {data.downloads.mac_arm && <a href={data.downloads.mac_arm} target="_blank" rel="noreferrer">🍎 macOS (Apple Silicon) .dmg</a>}
          {data.downloads.mac_intel && <a href={data.downloads.mac_intel} target="_blank" rel="noreferrer">🍎 macOS (Intel) .dmg</a>}
          <button className="underline" onClick={() => check(true)}>↻ ពិនិត្យឡើងវិញ</button>
        </div>
      )}
    </div>
  );
}

/** ប៊ូតុងតូចក្នុង header — បង្ហាញជានិច្ចពេលមានកំណែថ្មី */
export function UpdatePill({ upd }) {
  const data = upd?.data;
  if (!data || !data.available) return null;
  return (
    <a href={data.url} target="_blank" rel="noreferrer" className="btn text-xs !py-1"
      title={`មានកំណែថ្មី v${data.latest} — អ្នកប្រើ v${data.current} · ចុចដើម្បីទាញយក`}
      style={{ background: "linear-gradient(135deg,#34d399,#22d3ee)", color: "#052e1b", fontWeight: 700 }}>
      🎁 v{data.latest}
    </a>
  );
}

/** ផ្នែកក្នុង Settings — កំណែបច្ចុប្បន្ន + ពិនិត្យដោយដៃ */
export function UpdateBox() {
  const upd = useUpdate({ delay: 200 });
  const { data, busy, check } = upd;
  const ok = data && data.ok;
  const avail = !!(data && data.available);
  return (
    <div className="glass p-3" style={{ borderLeft: "4px solid #34d399" }}>
      <div className="text-sm font-semibold flex items-center gap-2">
        🔄 កំណែកម្មវិធី
        <button className="btn ghost text-xs !py-0.5 ml-auto" disabled={busy} onClick={() => check(true)}>
          {busy ? "កំពុងពិនិត្យ…" : "↻ ពិនិត្យកំណែថ្មី"}
        </button>
      </div>
      <div className="text-xs mt-1.5 space-y-1">
        <div>កំពុងប្រើ៖ <b>v{data?.current || "…"}</b></div>
        {ok && !avail && <div style={{ color: "#6ee7b7" }}>✅ អ្នកកំពុងប្រើកំណែថ្មីបំផុត (v{data.latest})</div>}
        {ok && avail && (
          <div style={{ color: "#fbbf24" }}>
            🎁 មានកំណែថ្មី <b>v{data.latest}</b> —{" "}
            <a className="underline" href={data.downloads?.windows || data.url} target="_blank" rel="noreferrer">ទាញយក Windows</a>
            {data.downloads?.mac_arm && <> · <a className="underline" href={data.downloads.mac_arm} target="_blank" rel="noreferrer">macOS (Apple)</a></>}
            {data.downloads?.mac_intel && <> · <a className="underline" href={data.downloads.mac_intel} target="_blank" rel="noreferrer">macOS (Intel)</a></>}
          </div>
        )}
        {data && !ok && (
          <div style={{ color: "#fca5a5" }}>
            ⚠ ពិនិត្យមិនបាន (គ្មាន internet ឬ GitHub បិទ) —{" "}
            <a className="underline" href={data.url} target="_blank" rel="noreferrer">បើកទំព័រទាញយក</a>
            {data.latest && <> · ដឹងចុងក្រោយ v{data.latest}{data.available ? " (ថ្មីជាង)" : ""}</>}
          </div>
        )}
      </div>
    </div>
  );
}
