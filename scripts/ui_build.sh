#!/usr/bin/env bash
# Rebuild UI (frontend/dist) — ត្រូវរត់ក្រោយ `git pull` ព្រោះ dist មិនចូល git
# ប្រើ:  bash scripts/ui_build.sh        (ក្នុង folder repo)
set -e
cd "$(dirname "$0")/../frontend"
if [ ! -d node_modules ]; then
  echo "→ npm install (ដំបូងតែម្តង)…"
  npm install
fi
echo "→ npm run build"
npm run build
echo "✅ UI ថ្មីរួចរាល់ — សូម restart app ឬចុច Ctrl/Cmd+R"
