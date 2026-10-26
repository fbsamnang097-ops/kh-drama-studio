import { defineConfig } from "vite"; import react from "@vitejs/plugin-react";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

// Embed the actual source version into the React bundle; the footer can then
// distinguish a current backend with a stale frontend bundle. Docker and
// frontend-only build contexts may omit the root VERSION, so fall back to the
// frontend package version there.
const rootVersion = fileURLToPath(new URL("../VERSION", import.meta.url));
const packageJson = fileURLToPath(new URL("./package.json", import.meta.url));
const UI_BUILD_VERSION = existsSync(rootVersion)
  ? readFileSync(rootVersion, "utf8").trim()
  : JSON.parse(readFileSync(packageJson, "utf8")).version;
if (!UI_BUILD_VERSION) throw new Error("Cannot determine UI build version");

export default defineConfig({
  plugins: [react()],
  define: { __UI_BUILD_VERSION__: JSON.stringify(UI_BUILD_VERSION) },
  build: {
    // Safari iOS ចាស់ៗនៅតែមានលើ PWA ដែលដំឡើងពី Home Screen។
    // បម្លែង JavaScript syntax ដើម្បីឱ្យ bundle អាច parse បានចាប់ពី Safari 13។
    target: "safari13",
    outDir: "dist",
    emptyOutDir: true
  },
  root: ".",
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/files": "http://127.0.0.1:8000"
    }
  }
})