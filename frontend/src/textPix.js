// អក្សរខ្មែរ → PNG គុណភាពខ្ពស់ (គូរក្នុង browser ដើម្បីមិនពឹង font របស់ FFmpeg)
// targetW = ទទឹងវីដេអូពិត (px), sizePct = ទទឹងអក្សរជា % នៃវីដេអូ → PNG ត្រូវនឹងទំហំដែលដាក់ (1:1)
export async function renderTextPng(text, color = "#ffffff", targetW = 1080, sizePct = 50) {
  const t = String(text || "");
  if (!t.trim()) return "";
  try { await document.fonts.load("600 64px 'Noto Sans Khmer'"); } catch { /* ប្រើ font ប្រព័ន្ធ */ }
  const fs = 64, pad = 16, lh = Math.round(fs * 1.5);
  const font = `600 ${fs}px 'Noto Sans Khmer','Noto Sans SC',sans-serif`;
  const cv = document.createElement("canvas"), m = cv.getContext("2d");
  m.font = font;
  const lines = t.split("\n");
  const nw = Math.max(10, Math.ceil(Math.max(...lines.map((l) => m.measureText(l).width))) + pad * 2);
  const target = Math.max(48, Math.round((targetW || 1080) * Math.min(100, Math.max(1, sizePct || 50)) / 100));
  const k = Math.min(8, Math.max(0.5, target / nw));   // ពង្រីក canvas ឱ្យត្រូវនឹង px ពិត
  cv.width = Math.round(nw * k); cv.height = Math.round((lh * lines.length + pad) * k);
  const c = cv.getContext("2d");
  c.setTransform(k, 0, 0, k, 0, 0);
  c.font = font; c.textAlign = "center"; c.textBaseline = "middle"; c.lineJoin = "round";
  c.lineWidth = fs * 0.16; c.strokeStyle = "#000"; c.fillStyle = color;
  lines.forEach((l, i) => {
    const y = pad / 2 + lh * i + lh / 2;
    c.strokeText(l, nw / 2, y); c.fillText(l, nw / 2, y);
  });
  return cv.toDataURL("image/png");
}
