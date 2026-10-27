import { useState } from "react";

const AGE_ICON = { child: "🧒", teen: "🧑", adult: "🧑‍💼", elderly: "👴", unknown: "❔" };
const GEN_ICON = { male: "♂", female: "♀", unknown: "?" };

/** ប្រអប់ Character / Voice Assignment
 *  · តួអង្គ → ភេទ · អាយុ · សំឡេង · 🔊 សាកស្តាប់ · ជ្រើសដោយដៃ
 *  · Toggle ស្កេនស្វ័យប្រវត្តិ · Auto Assign Voice · Re-detect Characters
 */
export default function CharacterPanel({ cast = [], cat = {}, onDetect, onAutoAssign, onAssign, onPreview, auto, setAuto, busy, msg, onClose }) {
  const [pv, setPv] = useState("");
  const voices = cat.voices || [];
  const ages = cat.ages || {};
  const genders = cat.genders || {};
  const limits = cat.limitations || [];

  const preview = async (id) => {
    setPv(id);
    try { await onPreview(id); } catch (e) { alert(e.message); }
    setPv("");
  };

  return (
    <div className="rounded-xl p-3 mb-2" style={{ background: "rgba(139,92,246,.10)", border: "1px solid rgba(139,92,246,.35)" }}>
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <b className="text-sm" style={{ color: "#c4b5fd" }}>🎭 តួអង្គ &amp; សំឡេង</b>
        <label className="flex items-center gap-1 text-xs cursor-pointer select-none" title="ស្កេនតួអង្គស្វ័យប្រវត្តិក្រោយ Transcribe">
          <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} />
          ស្កេនស្វ័យប្រវត្តិ
        </label>
        <button className="btn text-xs !py-0.5" style={{ background: "#8b5cf6", color: "#fff" }} disabled={!!busy} onClick={onDetect}>🔍 Re-detect Characters</button>
        <button className="btn ghost text-xs !py-0.5" disabled={!!busy} onClick={onAutoAssign}>✨ Auto Assign Voice</button>
        <button className="btn ghost text-xs !py-0.5 ml-auto" onClick={onClose}>✕</button>
        <span className="text-xs opacity-70">{busy}</span>
      </div>

      {msg && <div className="text-xs mb-2" style={{ color: "#6ee7b7" }}>{msg}</div>}

      {!cast.length ? (
        <div className="text-xs opacity-70">
          មិនទាន់មានទិន្នន័យតួអង្គ — សូម Upload វីដេអូ រួច Transcribe (ឬចុច Re-detect)។
        </div>
      ) : (
        <div className="overflow-auto" style={{ maxHeight: 220 }}>
          <table className="w-full text-xs">
            <thead>
              <tr className="opacity-70 text-left">
                <th className="p-1">#</th><th className="p-1">តួអង្គ</th><th className="p-1">ភេទ</th>
                <th className="p-1">អាយុ</th><th className="p-1">សំឡេង</th><th className="p-1">បន្ទាត់</th>
                <th className="p-1">ភាពជឿជាក់</th><th className="p-1">សាកស្តាប់</th>
              </tr>
            </thead>
            <tbody>
              {cast.map((c) => (
                <tr key={c.id} className="border-t" style={{ borderColor: "rgba(255,255,255,.08)" }}>
                  <td className="p-1"><i className="dot" style={{ background: c.color || "#a78bfa" }} />{c.id}</td>
                  <td className="p-1 whitespace-nowrap">
                    <b>{c.name}</b>
                    {c.kind === "narrator" && <span className="opacity-60"> · អ្នកនិទាន</span>}
                    {c.manual && <span title="ជ្រើសដោយដៃ — រក្សារហូតដល់ Auto Assign Voice" style={{ color: "#fbbf24" }}> ✋</span>}
                    {!c.manual && <span title="ស្វ័យប្រវត្តិ — តាមភេទ/អាយុពីសំឡេង" style={{ color: "#34d399" }}> ⚙</span>}
                    {c.conflict && <span title="អត្ថបទផ្ទុយនឹងសំឡេង" style={{ color: "#fb7185" }}> ⚠</span>}
                    {c.corrected && <span title={`កែព័ត៌មានតួអង្គ (${c.corrected})`} style={{ color: "#38bdf8" }}> ✎</span>}
                    {(c.voice_mismatch || (["male", "female"].includes(c.gender) && voices.some((v) => v.id === c.voice && v.gender && v.gender !== "unknown" && v.gender !== c.gender))) && <span title="សំឡេងដែលជ្រើសដោយដៃ ខុសភេទនឹងការវិភាគ — ការចាត់សំឡេង Apply All គឺជាការជ្រើសដោយដៃ" style={{ color: "#f97316" }}> ⚑</span>}
                  </td>
                  <td className="p-1">{GEN_ICON[c.gender] || "?"} {genders[c.gender] || c.gender}</td>
                  <td className="p-1">{AGE_ICON[c.age] || ""} {ages[c.age] || c.age}</td>
                  <td className="p-1">
                    <select className="ghost !py-0.5 !px-1 text-xs" value={c.voice}
                      onChange={(e) => onAssign(c.id, e.target.value)} disabled={!!busy}>
                      {voices.map((v) => (
                        <option key={v.id} value={v.id}>
                          {v.label} — {genders[v.gender] || v.gender} · {ages[v.age] || v.age}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="p-1">{c.lines}</td>
                  <td className="p-1">
                    <span title={`${Math.round((c.conf || 0) * 100)}%`} style={{
                      display: "inline-block", width: 46, height: 6, borderRadius: 3,
                      background: "rgba(255,255,255,.15)", verticalAlign: "middle",
                    }}>
                      <i style={{
                        display: "block", height: 6, borderRadius: 3,
                        width: `${Math.round((c.conf || 0) * 100)}%`,
                        background: (c.conf || 0) > 0.7 ? "#34d399" : (c.conf || 0) > 0.45 ? "#fbbf24" : "#fb7185",
                      }} />
                    </span>
                  </td>
                  <td className="p-1">
                    <button className="btn ghost !py-0.5 !px-2 text-xs" disabled={pv === c.voice}
                      onClick={() => preview(c.voice)}>{pv === c.voice ? "…" : "🔊"}</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="text-[11px] mt-2 opacity-60">
        សំឡេងត្រូវបានរក្សាទុកក្នុងគម្រោង (SQLite) — តួអង្គដដែលប្រើសំឡេងដដែលគ្រប់ឆាក ·
        ជ្រើសដោយដៃនៅទីនេះឈ្នះស្វ័យប្រវត្តិ រហូតដល់ចុច “✨ Auto Assign Voice”។
        {cat.provider?.provider ? ` · provider: ${cat.provider.provider}${cat.provider.verified ? " ✓ verified" : " (offline)"}` : ""}
      </div>

      {limits.length > 0 && (
        <div className="text-[11px] mt-2 opacity-70" style={{ color: "#fbbf24" }}>
          ⚠ {limits.map((l, i) => <div key={i}>· {l}</div>)}
        </div>
      )}
    </div>
  );
}
