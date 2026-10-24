// Layer ទាំង ៥ ប្រភេទ + ការកំណត់ដើម — ប្រើដោយ OverlayPanel (preview) និង App (Export)
export const CYAN = "#22d3ee", GOLD = "#fbbf24", RED = "#f43f5e", VIOLET = "#a78bfa", PINK = "#f472b6";

export const POS = {
  "Top Left": [3, 4], "Top Center": [50, 4], "Top Right": [97, 4],
  "Center Left": [3, 50], "Center": [50, 50], "Center Right": [97, 50],
  "Bottom Left": [3, 85], "Bottom Center": [50, 85], "Bottom Right": [97, 85],
};

// លំដាប់ដាក់: ក្រោយ = លើគេ (ដូច backend/graph.py: LAYER_ORDER)
export const LAYERS = [
  { k: "logo", label: "🏷️ Logo", c: CYAN, def: { pos: "Top Right", x: 97, y: 4, size: 15, op: 90 } },
  { k: "sponsor", label: "⭐ Sponsor", c: GOLD, def: { pos: "Bottom Left", x: 3, y: 85, size: 25, op: 90 } },
  { k: "overlay", label: "🖼️ Overlay", c: CYAN, def: { pos: "Bottom Center", x: 50, y: 85, size: 25, op: 90 } },
  { k: "text", label: "©️ Khmer Text", c: VIOLET, def: { pos: "Bottom Center", x: 50, y: 92, size: 50, op: 100 } },
];

export const KIND_ICON = { logo: "🏷️ Logo", sponsor: "⭐ Sponsor", overlay: "🖼️ Overlay", text: "©️ Khmer Text" };

export const initLayers = () => Object.fromEntries(LAYERS.map((L) => [L.k, { on: false, url: "", name: "", text: "", color: "#ffffff", ...L.def }]));

// វីដេអូថ្មី → លុប file layer ចាស់ (ជារបស់វីដេអូមុន) តែរក្សាការកំណត់ (ទីតាំង/ទំហំ)
export const resetLayers = (st) => Object.fromEntries(Object.entries(st).map(([k, v]) => [k, k === "text" ? v : { ...v, url: "", name: "", on: false }]));
