import { defineConfig } from "vite"; import react from "@vitejs/plugin-react";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

// Embed the actual source version into the React bundle; the footer can then
// distinguish a current backend with a stale frontend bundle.
const UI_BUILD_VERSION = readFileSync(fileURLToPath(new URL("../VERSION", import.meta.url)), "utf8").trim();

export default defineConfig({
  plugins: [react()],
  define: { __UI_BUILD_VERSION__: JSON.stringify(UI_BUILD_VERSION) },
  build: {
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