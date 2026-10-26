import { readFile, readdir } from "node:fs/promises";
import { Window } from "happy-dom";

const assetDir = new URL("../dist/assets/", import.meta.url);
const files = await readdir(assetDir);
const bundleName = files.find((name) => /^index-.*\.js$/.test(name));
if (!bundleName) throw new Error("Production UI bundle is missing; run the Vite build first.");
const bundle = await readFile(new URL(bundleName, assetDir), "utf8");

const browser = new Window({ url: "https://kh-drama-studio.test/" });
browser.document.body.innerHTML = '<div id="root"></div>';
browser.fetch = async () => ({ ok: false, status: 503, json: async () => ({}) });
// happy-dom does not implement canvas; return the small API used by the initial BGM effect.
browser.HTMLCanvasElement.prototype.getContext = () => ({
  clearRect() {}, fillRect() {}, beginPath() {}, moveTo() {}, lineTo() {}, stroke() {}, fillText() {},
  createLinearGradient() { return { addColorStop() {} }; },
  measureText(text) { return { width: String(text).length * 8 }; },
});
browser.HTMLCanvasElement.prototype.toDataURL = () => "data:image/png;base64,";

const errors = [];
browser.console.error = (...args) => errors.push(args.map(String).join(" "));
browser.addEventListener("error", (event) => {
  errors.push(`${event.message}: ${event.error?.stack || ""}`);
});
browser.addEventListener("unhandledrejection", (event) => errors.push(String(event.reason)));

try {
  browser.eval(bundle);
  await new Promise((resolve) => setTimeout(resolve, 500));
  const root = browser.document.getElementById("root");
  if (!root?.childElementCount) errors.push("React did not mount any UI into #root.");
  if (errors.length) throw new Error(`UI mount smoke test failed:\n${errors.join("\n")}`);
  console.log("UI mount smoke test passed.");
} finally {
  browser.happyDOM.abort();
}
