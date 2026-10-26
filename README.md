# kh-drama-studio

ឧបករណ៍បង្កើតវីដេអូរឿងខ្មែរដោយស្វ័យប្រវត្តិ ដោយប្រើ API ឥតគិតថ្លៃ។

**លំហូរ:** ប្រធានបទ → ស្គ្រីប → រូបភាព → សំឡេងខ្មែរ → subtitle → វីដេអូ

## API ដែលប្រើ

| ផ្នែក | សេវា | Key |
|---|---|---|
| ស្គ្រីប | Gemini API (free tier) | ត្រូវការ `GEMINI_API_KEY` |
| រូបភាព | Gemini image model, បម្រុងដោយ Pollinations | Pollinations មិនត្រូវការ key |
| សំឡេងខ្មែរ | edge-tts | មិនត្រូវការ key (មិនមែន API ផ្លូវការ) |
| Subtitle | បង្កើតពីស្គ្រីបផ្ទាល់ (`.srt`) | មិនត្រូវការ |
| វីដេអូ | FFmpeg | ដំឡើងក្នុង Mac |

> Free tier ប្តូរញឹកញាប់ ហើយមានកម្រិតស្នើក្នុងមួយនាទី។ បើជួប error 429 សូមរង់ចាំមួយនាទីរួចសាកម្តងទៀត។

## ដំឡើង

```bash
brew install ffmpeg
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install edge-tts python-dotenv requests
cp .env.example .env     # រួចដាក់ GEMINI_API_KEY ក្នុង .env
```

យក key ឥតគិតថ្លៃនៅ Google AI Studio (aistudio.google.com)។

## រត់

```bash
python pipeline.py "រឿងស្នេហាក្នុងភូមិមួយ នៅខេត្តសៀមរាប" --scenes 5
```

លទ្ធផលនៅក្នុង `storage/output/`:
- `final.mp4` វីដេអូចុងក្រោយ
- `subtitles.srt` subtitle
- `script.json` ស្គ្រីប

## សុវត្ថិភាព

- ដាក់ API key ក្នុង `.env` ប៉ុណ្ណោះ (ត្រូវបាន ignore ដោយ git)
- កុំ commit `.env`, `.venv/`, `node_modules/`, `storage/`

---

## Web App (FastAPI + React): រត់លើ Mac និង Windows

Web app សម្រាប់ Upload វីដេអូ → Transcribe (ចិន) → បកប្រែខ្មែរ → សំឡេងខ្មែរ (TTS) → Export ជាមួយ BGM និង subtitle។

### តម្រូវការ

- Python 3.10+ (សាកល្បងជាមួយ 3.12)
- Node.js 18+ (សម្រាប់ build frontend)
- FFmpeg (ត្រូវនៅក្នុង PATH)
- ជម្រើស: `demucs` សម្រាប់ដកសំដីចេញពី BGM (ធ្ងន់ បើគ្មានវា app ប្រើ filter ffmpeg ធម្មតាជំនួស)

### macOS

```bash
brew install python node ffmpeg

git clone https://github.com/fbsamnang097-ops/kh-drama-studio.git
cd kh-drama-studio

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd frontend && npm install && npm run build && cd ..

PYTHONPATH=. python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### Windows (PowerShell)

```powershell
winget install Python.Python.3.12 OpenJS.NodeJS Gyan.FFmpeg
# បិទ ហើយបើក PowerShell ឡើងវិញក្រោយដំឡើង

git clone https://github.com/fbsamnang097-ops/kh-drama-studio.git
cd kh-drama-studio

python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

cd frontend; npm install; npm run build; cd ..

$env:PYTHONPATH = "."
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

បើ PowerShell ទប់ស្កាត់ script activate សូមរត់ម្តង៖
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### បើកប្រើ

បើក http://127.0.0.1:8000 ចុចរូប ⚙️ រួចដាក់ API key (បកប្រែ, STT, TTS)។ Key រក្សាទុកក្នុងម៉ាស៊ីនអ្នកតែប៉ុណ្ណោះ។

### បញ្ឈប់ / ចាប់ផ្តើមឡើងវិញ

ចុច `Ctrl+C` ក្នុង terminal រួចរត់ពាក្យបញ្ជាចុងក្រោយម្តងទៀត។
បន្ទាប់ពីកែ frontend ត្រូវរត់ `npm run build` ហើយ refresh ដោយ `Cmd+Shift+R` (Mac) ឬ `Ctrl+Shift+R` (Windows)។

### ជម្រើស: ដកសំដីពី BGM ឱ្យស្អាតជាង

```bash
pip install demucs
```

លើ Mac បើ install បរាជ័យពេល build `sphn` សូមប្រើ៖
`CMAKE_POLICY_VERSION_MINIMUM=3.5 pip install demucs`

* * *

## 🎭 តួអង្គ & សំឡេងថេរ — SQLite Registry (v1.0.18)

តួអង្គម្នាក់ = **ID មួយ** + **សំឡេងមួយ** ពេញរឿង និងឆ្លងការ restart · reload · បកប្រែឡើងវិញ · export។
v1.0.18 ដោះស្រាយបញ្ហាចម្បង៖ តួអង្គដដែលធ្លាយបាត់ ID ពេលឆ្លងឆាក និងសំឡេងប្តូរតាម segment។

### ស្ថាបត្យកម្ម
```
video ──► diarize.py ─────► scenes.py ──► identity.py ──► registry.py (SQLite)
         (F0 · ZCR ·         (ឆាក)        (ភ្ជាប់តួអង្គ)   (ID + សំឡេង ថេរ)
          k-means)
                                              │
        អត្ថបទចិន ───────────────────────────┘
                                              ▼
                         /api/tts (char_id) ──► providers.tts() ──► mp3
                                              ▼
                         /api/export ──► {video}.voices.json (manifest)
```

### ១. បែងចែកអ្នកនិយាយ (`backend/diarize.py`)
- ffmpeg → s16le 8 kHz → **autocorrelation F0** + ZCR + voiced ratio (pure Python)
- **k-means គ្មាន random** (ចាប់ផ្តើមពី quantile F0) + **silhouette** ជ្រើស k ល្អបំផុត
- distance = `|Δlog(F0)| / 0.15 + |ΔZCR| / 0.06`
- clustering ជា **global** (គ្រប់ឆាក) → តួអង្គនៅឆាក ១ · ៥ · ១២ = cluster តែមួយ

### ២. ឆាក (`backend/scenes.py` · ថ្មី)
`ffmpeg select='gt(scene,0.35)'` → បើរកមិនឃើញ → ចន្លោះសម្ងាត់ > 2.5 វិនាទី → បើគ្មាន → ១ ឆាក។
បង្ហាញចំនួនឆាកក្នុងប្រអប់ 🎭 និងប្រើសម្រាប់ភ្ជាប់តួអង្គឆ្លងឆាក។

### ៣. Registry (`backend/registry.py` · ថ្មី) — SQLite
`DATA/kh_drama.db` (dev = root repo · app = `%APPDATA%\KHDramaStudio`)

| តារាង | ជួរឈរ |
|---|---|
| `projects` | pid · video · created · updated |
| `characters` | **cid** · pid · name · gender · age · role · voice_provider · **voice_id** · **auto_voice** · assignment(auto/manual) · conf · fp_f0 · fp_zcr · first_seen · last_seen |
| `segments` | pid+idx · cid · voice_id · start · end · zh · km · audio |

ការភ្ជាប់តួអង្គ (identity)៖
1. **ឈ្មោះដូចគ្នា** ក្នុងគម្រោង → តួអង្គដដែល
2. គ្មានឈ្មោះ → **fingerprint (F0 + ZCR)** → តួអង្គដដែល
3. ខុសគ្នាពិត → ID ថ្មី (`c1`, `c2`, … មិនជាន់លេខចាស់)
4. **manual ឈ្នះជានិច្ច** — `upsert_character(keep_voice=True)` មិនប៉ះសំឡេងដៃ
5. `reset_manual` → ត្រឡប់ទៅ `auto_voice` ដើម (មិនរក្សាសំឡេងជ្រើសដៃ)

### ៤. សំឡេង & provider (`backend/voices.py` · `providers.py`) — ១៩ profile

| ក្រុម | សំឡេង | rate | pitch | volume |
|---|---|---|---|---|
| 👨 ប្រុសពេញវ័យ ×៣ | Piseth | 0 / −5 / +4% | 0 / −9 / +8Hz | +0% |
| 👩 ស្រីពេញវ័យ ×៣ | Sreymom | 0 / −4 / +3% | 0 / −6 / +7Hz | +0% |
| 👴 ចាស់ប្រុស ×២ | Piseth | −18 / −22% | −24 / −30Hz | −6/−8% |
| 👵 ចាស់ស្រី ×២ | Sreymom | −16 / −20% | −19 / −26Hz | −6/−8% |
| 👦 ក្មេងប្រុស ×២ | Piseth | +12 / +16% | +42 / +50Hz | +4% |
| 👧 ក្មេងស្រី ×២ | Sreymom | +10 / +14% | +38 / +46Hz | +4% |
| 🧑 យុវជន/យុវនារី | Piseth/Sreymom | +7% | +16/14Hz | +1% |
| 📖 អ្នកនិទាន ×២ | Piseth/Sreymom | −7/−6% | −8/−6Hz | −2% |
| ❔ មិនដឹង | Piseth | −3% | −3Hz | −3% |

- ភេទ **មិនដែលប្តូរ**៖ ចាស់ស្រី → Sreymom ជានិច្ច · ចាស់ប្រុស → Piseth ជានិច្ច
- `GET /api/voices` → **provider voices ពិត** (`edge_tts.list_voices`) + `verified` + `limitations`
- អត់ internet → `verified:false` និងបង្ហាញតែ voice id ដែលដឹងច្បាស់ (មិនប្រឌិត)
- `KH_TTS_STUB=1` → tone offline **សម្រាប់តេស្តតែប៉ុណ្ណោះ**

### ៥. API
| Method | Path | ការងារ |
|---|---|---|
| POST | `/api/characters/detect` | `{id, project, segments, use_audio, reassign}` → តួអង្គ + items + scenes + provider |
| POST | `/api/characters/assign` | `{id, project, overrides:{cid:voice}, reset}` → manual រក្សាក្នុង DB |
| GET | `/api/project/{pid}` | ផ្ទុកតួអង្គ + segments ឡើងវិញ (ក្រោយ restart) |
| GET | `/api/export_manifest?id=` | បន្ទាត់ → តួអង្គ → សំឡេងដែលប្រើពិត (`match`) |
| GET | `/api/voices` · POST `/api/voices/refresh` | provider voices ពិត + ដែនកំណត់ |
| POST | `/api/segments/fix` | `{id, segments}` → កាត់បន្ទាត់វែង ≤ ៨ វិនាទី (ប្រើសំឡេងពិត) |
| POST | `/api/tts` | `{text, char_id, video, idx}` → **សំឡេងពី DB** + កត់ត្រា segment |
| POST | `/api/voice_preview` | `{voice, text}` → mp3 សាកស្តាប់ |

### ៦. UI — 🎭 តួអង្គ & សំឡេង
- តារាង៖ `#` · ឈ្មោះ · ភេទ · អាយុ · **សំឡេង (dropdown ក្នុងប្រអប់តែប៉ុណ្ណោះ)** · បន្ទាត់ · ភាពជឿជាក់ · 🔊
- `⚙` ស្វ័យប្រវត្តិ · `✋` ជ្រើសដៃ · `✎` កែភេទ/អាយុ · `⚑` សំឡេងដៃខុសភេទ · `⚠` អត្ថបទផ្ទុយសំឡេង
- **🔍 Re-detect Characters** · **✨ Auto Assign Voice** (reset → auto) · **☑ ស្កេនស្វ័យប្រវត្តិ**
- ជួរ Character ក្នុងតារាងបន្ទាត់ ជា **read-only** (គ្មាន dropdown)
- ក្រោយ reload វីដេអូ → ទាញការចាត់សំឡេងពី SQLite ដោយស្វ័យប្រវត្តិ

### ៦.៥ បន្ទាត់វែង + ភេទសំឡេងតួអង្គ (v1.0.24) — “ស្រីឮប្រុស / ប្រុសឮស្រី” ដាច់ខាត

បញ្ហាដែលអ្នកប្រើរាយការណ៍៖ បន្ទាត់ `#1 Start 5.3 → End 41.0` (៣៥,៧ វិនាទី) តែអត្ថបទត្រឹម `终结`
ហើយពេល Dubbing **ស្រីឮសំឡេងប្រុស · ប្រុសឮសំឡេងស្រី**។ មូលហេតុពិត ២៖

| មូលហេតុ | ដំណោះស្រាយ |
|---|---|
| STT (faster-whisper) ត្រឡប់បន្ទាត់វែង ៣៥ វិនាទី គ្របលើអ្នកនិយាយច្រើន → សំឡេងតួអង្គតែមួយសម្រាប់ទាំងអស់ | `backend/segments.py` 🆕 — `fit()` កាត់គ្រប់បន្ទាត់ ≤ **៨ វិនាទី** ត្រង់ចន្លោះស្ងាត់ តាមសំឡេងពិត (ffmpeg) |
| អត្ថបទ STT គ្មាន `「」` → `cast.detect()` ចាត់ជា **“អ្នកនិទាន”** ស្ទើរទាំងអស់ → បន្ទាត់ស្រីទាំងអស់យកសំឡេងអ្នកនិទាន (ប្រុស) | `identity.resolve()` — **សំឡេងជាអ្នកសម្រេចភេទ** (អាទិភាព ១) មិនមែនអត្ថបទ · + gender guard ក្នុងគ្រប់បន្ទាត់ |

- `AUDIO_MIN 0.55` → សំឡេងច្បាស់ = ភេទបន្ទាត់ · `GUARD_MIN 0.65` → បន្ទាត់ដែលជំទាស់ cluster ផ្លាស់ទៅតួអង្គភេទខ្លួនឯង
- អ្នកនិទានពិត (`旁白`/`画外音`) → បំបែកបាន **២ សំឡេង** (ប្រុស + ស្រី) តាមសំឡេងពិត · រក្សាក្នុង DB
- `diarize.speech_window()` — បន្ទាត់ចាស់វែង (> ៩ វិ) វិភាគតែចន្លោះសំឡេងខ្លាំងបំផុត → ភេទមិនលាយ
- `POST /api/segments/fix` 🆕 · ប៊ូតុង **✂️ កាត់វេនវែង** — ជួសជុលគម្រោងចាស់ដោយមិនចាំបាច់ Transcribe ម្តងទៀត
- `P.tts` — របៀបធម្មតា (NATURAL) **គ្មាន prosody តាមបន្ទាត់** → សំឡេងតួអង្គ **ដដែលគ្រប់បន្ទាត់**
- `_voice_for()` — គ្មាន voice ក្នុង DB/cast → ប្រើ role code ឬភេទ → `male_adult_1`/`female_adult_1` (មិនធ្លាក់ទៅ Piseth ដោយស្វ័យប្រវត្តិ)

```
$ python tests/test_segments.py     → 19 passed, 0 failed
$ python tests/test_characters.py   → 23 passed, 0 failed
$ python tests/test_dubbing.py      → 15 passed, 0 failed
$ python tests/test_updates.py      → 16 passed, 0 failed
```

### ៦.៦ Windows Release — ត្រួតពិនិត្យ version និង UI មុន publish

Screenshot ដែលបង្ហាញ footer `v1.0.24` ប៉ុន្តែមិនមានប៊ូតុង `✂️ កាត់វេនវែង`/`🎭 តួអង្គ` បញ្ជាក់ថា backend ថ្មី និង frontend ចាស់អាចច្រឡំគ្នាបាន។ ចាប់ពី v1.0.25 តទៅ workflow `desktop.yml` ពិនិត្យ **EXE backend ដែលទើប build** ដោយ៖

- ប្រៀបធៀប `/api/version` ទៅ `VERSION` របស់ tag
- ទាញ `/` និង JS bundle ពិតពី EXE ហើយពិនិត្យថាមាន `/api/segments/fix` និង `/api/characters/detect`
- ប្រៀបធៀបឈ្មោះ bundle ក្នុង HTML ជាមួយ `/api/version` — ខុសមួយណា build នឹង fail មុន publish

តេស្តដូចគ្នារត់ដោយ `python scripts/check_packaged_ui.py http://127.0.0.1:8731`។ ការទាញយក Windows ត្រូវជ្រើស `KH-Drama-Studio-vX.Y.Z.exe` ក្នុង Release ថ្មីបំផុត ហើយបើកពី Start Menu ក្រោយដំឡើង។

### ៦.៤ ជូនដំណឹងកំណែថ្មី (v1.0.23) — អ្នកប្រើដឹង និងទាញយកបានភ្លាម
រាល់ពេលចេញកំណែថ្មី app **ប្រាប់អ្នកប្រើដោយខ្លួនឯង** — មិនត្រូវរង់ចាំគេសួរ។

| ស្រទាប់ | អ្វី |
|---|---|
| `backend/updates.py` 🆕 | `GET /api/update` ពិនិត្យ GitHub Releases (cache ៣០ នាទី · គ្មាន token) |
| បដាក្នុង app | 「🎁 មានកំណែថ្មី vX — អ្នកកំពុងប្រើ vY」 + **⬇ ទាញយក** (តាម OS) + អ្វីថ្មី + ផ្សាយពេលក្រោយ/មិនរំលឹក |
| Header | ប៊ូតុង **🎁 vX** ជាប់ពេលមានកំណែថ្មី (ចុច → ទំព័រ release) |
| Settings | ផ្នែក **🔄 កំណែកម្មវិធី** — កំណែបច្ចុប្បន្ន + ពិនិត្យដោយដៃ |
| Desktop (Electron) | Notification របស់ OS ម្តងក្នុងមួយកំណែ · ចុច → បើកទំព័រទាញយក |

- ពិនិត្យស្វ័យប្រវត្តិ៖ ពេលបើក app · រៀងរាល់ ៦ ម៉ោង · ពេលត្រឡប់មក app (≥ ៣០ នាទី)
- គ្មាន internet → មិនរំខាន (បង្ហាញតែក្នុង Settings ថា “ពិនិត្យមិនបាន” + តំណទំព័រទាញយក)
- តំណទាញយកជ្រើសតាម OS៖ `arm64.dmg` · `x64.dmg` · `.exe`
- `KH_UPDATE_OFFLINE=1` បិទ · `KH_UPDATE_URL`/`KH_UPDATE_REPO` សម្រាប់ mirror/តេស្ត

```
$ python tests/test_updates.py
16 passed, 0 failed — ALL UPDATE-NOTICE TESTS PASSED ✅
```

### ៦.៣ សំឡេងធម្មតា (v1.0.22) — Piseth / Sreymom ដូចដើម
ចាប់ពី v1.0.22 ការបញ្ចេញសំឡេងត្រឡប់ទៅ **សំឡេងពិតរបស់ provider** វិញ៖

| តួអង្គ | សំឡេង | rate/pitch/volume |
|---|---|---|
| ប្រុស (គ្រប់អាយុ) | **Piseth** · `male_adult_1` | 0 / 0 / 0 |
| ស្រី (គ្រប់អាយុ) | **Sreymom** · `female_adult_1` | 0 / 0 / 0 |
| មិនដឹង | Piseth · `unknown_1` | 0 / 0 / 0 |

- គ្មានកែ pitch/rate → សំឡេងធម្មតា មិនធ្ងន់/ស្តើងសិប្បនិម្មិត
- **ភេទមិនដែលប្តូរ** — ចាស់ស្រីនៅតែ Sreymom · ចាស់ប្រុសនៅតែ Piseth
- dropdown ក្នុងប្រអប់ 🎭 មានតែ ៣ ជម្រើស (ប្រុស · ស្រី · មិនដឹង)
- គម្រោងចាស់ (voice `elderly_female_1` …) → **normalize ស្វ័យប្រវត្តិ** តាមភេទ
- ចង់ត្រឡប់របៀបចាស់ (កែ pitch/rate) → `KH_VOICE_STYLE=varied`

### ៦.២ ការពារ UI ចាស់ (v1.0.20) — ហេតុអ្វីការកែមិនបង្ហាញ
`frontend/dist` មិនចូល git → `git pull` **មិន** ធ្វើបច្ចុប្បន្នភាព UI។ រួមជាមួយ cache របស់
Electron/browser នេះធ្វើឱ្យ app បង្ហាញ UI ចាស់ ទោះ backend ជា v1.0.20 រួចហើយ។

v1.0.20 ដោះស្រាយ ៣ ស្រទាប់៖
1. **`/api/version`** → `ui: {built, stale, bundle, built_at}` (ធៀប mtime `dist` នឹង `src`)
2. **`index.html` បញ្ជូនតាម backend** (មិនមែន StaticFiles) → បញ្ចូលបដា
   `⚠ UI ចាស់ — សូម rebuild` **ទោះ bundle ខ្លួនឯងជាកំណែចាស់**
3. **Cache headers** → `index.html`: `no-store` · `assets/*` (មាន hash): `immutable`
   → Electron/browser មិនអាចបង្ហាញ UI ចាស់ក្រោយ update ទៀតទេ

Rebuild UI ពេលរត់ពី source (ក្រោយ `git pull` ឬកែ frontend):
```bash
bash scripts/ui_build.sh        # ឬ: npm run ui:build   ឬ: cd frontend && npm run build
```
បើ backend ដើរ​ហើយ ហើយ UI ចាស់ → console បង្ហាញ `⚠ frontend/dist ចាស់ជាង frontend/src`
ហើយក្នុង app មានបដាក្រហមខាងក្រោម — ចុច `Ctrl/Cmd + R` ក្រោយ rebuild។

### ៦.១ Progress ពេល Export (v1.0.19)
- progress bar ពិត (%) បង្ហាញ **inline នៅខាងស្តាំ BGM** ក្នុងជួរឧបករណ៍ — មិនអណ្តែតលើ timeline ទៀតទេ
- ដក progress bar ចាស់ (`index.html` global loader) ចេញសម្រាប់ `/api/export` → មិនមានបារ​ស្ទួន
- បង្ហាញ៖ 🎬 Export · របារ · % · ETA (`~0:51`) · hover បង្ហាញល្បឿន (`1.75×`)
- រួចរាល់ → `✅ Export ចប់` រួចបាត់ទៅវិញក្នុង ១.៥ វិនាទី

### ៧. Acceptance Tests
```
$ python tests/test_dubbing.py     # Test 1–10 (server ពិត · ffmpeg ពិត · KH_TTS_STUB=1)
$ python tests/test_characters.py  # A–J + voicebook
```
- T1–T4៖ ចាស់ស្រី/ចាស់ប្រុស/ស្រីពេញវ័យ/ប្រុសពេញវ័យ — ឆ្លងឆាក ១ · ២ · ៣ → voice ដដែល
- T5–T7៖ ឆាកចម្រុះត្រូវតាម segment · ឆាកប្រុសតែម្នាក់គ្មានសំឡេងស្រី · ឆាកស្រីតែម្នាក់គ្មានសំឡេងប្រុស
- T8៖ generate ឡើងវិញ → voice ដដែល · T9៖ restart backend → រក្សាដដែល
- T10៖ export ពិត + `{video}.voices.json` → `voice_used == voice_expected`

```
14 passed, 0 failed — ALL DUBBING PIPELINE TESTS PASSED ✅
15 passed, 0 failed — ALL ACCEPTANCE TESTS PASSED ✅
```

### ៨. ដែនកំណត់ដែលត្រូវដឹង
- edge-tts មានសំឡេងខ្មែរ **តែ ២** (Piseth/Sreymom) → ចាស់/ក្មេង/តួប្រុស ២ នាក់
  បង្កើតដោយ `rate` + `pitch` + `volume` (ភេទត្រូវគ្នាជានិច្ច)
- ដើម្បីបានសំឡេងចាស់/ក្មេងពិត → កំណត់ Azure / Google / ElevenLabs ក្នុង Settings
- ការវិភាគ F0 ត្រូវអត្ថបទមានពេលវេលា (subtitle timestamps) — បើសំឡេងស្ងាត់ → `unknown`

## ⚡ Export លឿន (v1.0.14)

Export ត្រូវ encode វីដេអូទាំងមូល។ ដូច្នេះល្បឿនអាស្រ័យលើ encoder និង preset ច្រើនជាង layer/blur។
v1.0.14 ធ្វើឱ្យលឿនជាងមុន **~1.8–2.4 ដង** ដោយមិនប៉ះពាល់ដល់ខ្លឹមសារ៖

| អ្វីដែលផ្លាស់ | មុន | ឥឡូវ |
|---|---|---|
| Standard preset | `medium` crf 17 | `veryfast` crf 20 |
| Premium preset | `slow` crf 18 | `medium` crf 19 |
| HD 1080p | បង្ខំ `medium` | រក្សា preset របស់ tier |
| Layer រូបស្ងៀម | loop តាម framerate វីដេអូ | loop ១ fps (សន្សំ CPU) |

**⚡ របៀបលឿនបំផុត** — ក្នុងប្រអប់ Export ធីក **“⚡ លឿនបំផុត (ណែនាំ)”**:
ប្រើ `veryfast` + `crf 23` និង audio 160k → file តូចជាង លឿនជាង ហើយភ្នែកស្ទើរមិនឃើញខុស។

**Hardware encoder (ស្វ័យប្រវត្តិ)** — `backend/encode.py` សាកល្បង encode ពិត ០.៤ វិនាទី
ហើយជ្រើស encoder លឿនបំផុតដែលម៉ាស៊ីននោះប្រើបាន៖

| ម៉ាស៊ីន | Encoder | ល្បឿន (ប្រហែល) |
|---|---|---|
| Mac (Intel/M1-M4) | `h264_videotoolbox` | ៥–១៥× លឿនជាង CPU |
| NVIDIA GPU | `h264_nvenc` | ៥–១០× |
| Intel Quick Sync | `h264_qsv` | ៣–៨× |
| AMD (Windows) | `h264_amf` | ៣–៦× |
| គ្មាន GPU | `libx264` | ធម្មតា |

បើ hardware encoder បរាជ័យ → ត្រឡប់ទៅ `libx264` ស្វ័យប្រវត្តិ (មិនធ្វើឱ្យ Export ដួល)។
កំណត់ដោយដៃបាន៖ `KH_ENCODER=libx264` (ឬ `h264_nvenc`, `h264_videotoolbox`, ...)។
ស្ថានភាពបង្ហាញក្នុងប្រអប់ Export (ឧ. `⚡ VideoToolbox` ឬ `CPU (x264)`) និង `GET /api/encoder`។

**Progress ពិត + ETA** — Export ដំណើរការជា background job៖

- `POST /api/export` → `{"job": true}` ភ្លាមៗ (មិន block)
- `GET /api/export_status?id=<id>` → `{state, percent, eta, speed, url, error}`
- UI បង្ហាញ progress bar, `%`, និង `នៅសល់ ~mm:ss` ពី `-progress pipe:1` របស់ FFmpeg

**ឧទាហរណ៍វាស់ពិត** (វីដេអូ 30 វិនាទី 1080×1920, 2 CPU cores គ្មាន GPU, មាន subtitle + 4 layer + 2 blur + BGM):

| | មុន (v1.0.13) | ឥឡូវ (v1.0.14) |
|---|---|---|
| Standard | 34.1s (0.88×) | **14.4s (2.08×)** |
| Premium | 58.3s (0.51×) | **~19s (1.6×)** |

លើ Mac/Windows ដែលមាន GPU ល្បឿនកើនដល់ ៥–១៥× បន្ថែមទៀត។

## 🎬 Export តែមួយដង (Logo · Sponsor · Overlay · Khmer Text · Blur)

**គ្រប់យ៉ាងចេញក្នុង Export តែមួយ pass** — អក្សរខ្មែរ, សំឡេងខ្មែរ, BGM, layer ទាំង ៤ និង blur box
ត្រូវបានដាក់ក្នុង filter graph តែមួយ ដូច្នេះវីដេអូត្រូវ encode **តែម្តង** (លឿន និងគុណភាពមិនធ្លាក់)។
មិនត្រូវ Export រួចទើប Apply ម្តងមួយទៀតទេ។

របៀបប្រើ៖ កំណត់ layer និង blur ក្នុងប្រអប់ក្រោម preview → ចុច **Export Video** → ចប់។
ប្រអប់ Export បង្ហាញបញ្ជី ✅ នៃអ្វីដែលនឹងបញ្ចូល (អក្សរ, សំឡេង, BGM, Logo, Sponsor, Overlay, Text, Blur)។

លំដាប់គូរ (ក្រោម → លើ)៖ វីដេអូ → **Blur** → អក្សរខ្មែរ → **Logo → Sponsor → Overlay → Khmer Text**
ដូច្នេះ Blur បាំងតែអ្វីក្នុងវីដេអូដើម (មុខ, ស្លាក, អក្សរបរទេស) មិនបាំងអក្សរខ្មែរ ឬ logo របស់អ្នកទេ។

### 🎞️ Layers

tab 4 ក្នុងប្រអប់តែមួយ ហើយ layer នីមួយៗមានការកំណត់ផ្ទាល់ខ្លួន (បើក/បិទ, រូប, ទីតាំង, X, Y, ទំហំ, opacity) មិនជះឥទ្ធិពលគ្នា។

| Layer | ពិពណ៌នា |
|-------|---------|
| 🏷️ Logo | រូប PNG / JPG / WebP ឬវីដេអូ MP4 (loop) |
| ⭐ Sponsor | រូប PNG / JPG / WebP ឬវីដេអូ MP4 (loop) |
| 🖼️ Overlay | រូប ឬ GIF មានចលនា |
| ©️ Khmer Text | វាយអក្សរខ្មែរ ជ្រើសពណ៌បាន (គូរជា PNG ក្នុង browser មិនពឹង font របស់ FFmpeg) |

- Layer ទាំងអស់ត្រូវដាក់ក្នុង Export តាមលំដាប់ Logo → Sponsor → Overlay → Text
- Backend: `backend/graph.py` (filter graph តែមួយ), `backend/layers.py` (`POST /api/layer`)

### 🔲 Blur (ថេរ ឬដើរតាមចលនា)

tab **🔲 Blur** សម្រាប់បិទបាំងតំបន់ដែលមិនចង់ឱ្យឃើញ (មុខ, ឈ្មោះ, ស្លាក, logo)។

- **Add Blur Box** ហើយ **ចាប់ទាញ** ប្រអប់ដោយផ្ទាល់លើ preview។ ទាញការ៉េមាសជ្រុងក្រោមស្តាំដើម្បីប្តូរទំហំ (ដំណើរការទាំង mouse និង touch)
- កំណត់ទំហំ, កម្រិតព្រិល, និងពេលចាប់ផ្តើម/បញ្ចប់ (Start/End = ឥឡូវ)
- **🎯 Follow motion**: ប្រសិនបើវត្ថុរើ សូម play ទៅចំណុចផ្សេងៗ រួចទាញប្រអប់តាមវត្ថុ 3-5 ចំណុច។ ប្រព័ន្ធចាប់ keyframe ហើយគណនាចលនាកណ្តាលចន្លោះឱ្យ (មិនប្រើ AI)
- Blur ត្រូវបញ្ចូលក្នុង Export ដែរ (ដាក់ក្រោមអក្សរ និង layer)
- Backend: `backend/graph.py` (`_blur_filters`)
- Frontend: `frontend/src/BlurPanel.jsx`

### កែ layer / blur ក្រោយ Export រួច (ជម្រើស)

បើ Export រួចហើយ ចង់បន្ថែម ឬកែ layer / blur ដោយមិនចាំបាច់ Export សំឡេង និងអក្សរឡើងវិញ៖
ចុច **🎬 Apply Layers + Blur លើវីដេអូ Export រួច** → `POST /api/finish` → `<id>_km_fx.mp4`
(បញ្ចូលទាំង Layers និង Blur ក្នុង pass តែមួយ ហើយចាប់ផ្តើមពី `<id>_km.mp4` ដើមវិញ មិន encode ជាន់ៗ)។

Route ចាស់ (`/api/layers_apply`, `/api/overlay_apply`, `/api/blur_apply`) នៅដំណើរការ ប៉ុន្តែឥឡូវហៅ
`backend/finish.py` ដូចគ្នា ដូច្នេះមិន encode ច្រើនជាន់ទេ។

**ចំណាំ**
- ការកំណត់ Layers និង Blur រក្សាក្នុង browser តែប៉ុណ្ណោះ (មិនទាន់ save ទៅ project) ហើយ preview ក្នុង browser គ្រាន់តែជាការប៉ាន់ស្មាន
- បើមាន BGM ការ Export កាត់វីដេអូតាមរយៈពេលពិត (មិនរង់ចាំ loop ភ្លេងចប់)

## Deploy លើ Render

- Start command ប្រើ `uvicorn backend.main:app` ដូច្នេះ import ក្នុង `backend/` ត្រូវប្រើ relative (`from .layers import ...`)
- **ពេលបន្ថែម file ថ្មី ត្រូវ `git add` វាជានិច្ច** (ឧ. `backend/layers.py`, `backend/blur.py`) បើមិនដូច្នេះទេ deploy នឹងដួលដោយ `ModuleNotFoundError`
- ការកំណត់ដែលមាន key ត្រូវដាក់ក្នុង Render → **Environment** ជាអថេរមានបុព្វបទ `KH_` (ត្រូវបានអានជាការកំណត់ដូចក្នុង ⚙️)។ **កុំដាក់ key ក្នុង file ណាមួយនៅ GitHub** ហើយបើ key ណាធ្លាប់ឡើង GitHub ត្រូវ revoke រួចបង្កើតថ្មី
- STT អាចប្រើ Groq / OpenAI / custom (OpenAI-compatible) ឬ `local` (faster-whisper ធ្ងន់ មិនសមនឹង free tier)

### ដែនកំណត់ Render free tier

- Disk ត្រូវលុបពេល service ដេកហើយភ្ញាក់ឡើងវិញ ដូច្នេះ Export និង Apply (Layers / Blur) ត្រូវធ្វើក្នុង session តែមួយ
- Apply ត្រូវ encode វីដេអូម្តងទៀត ហើយ free tier យឺត សូមសាកល្បងជាមួយវីដេអូខ្លីសិន
- Auto tracking ពិតៗ (OpenCV) មិនទាន់មាន ព្រោះធ្ងន់ពេកសម្រាប់ RAM 512MB

* * *

## Clone និងរត់លើកដំបូង (Mac / Windows)

### 1. តម្រូវការ

| ឧបករណ៍ | កំណែ | ពិនិត្យ |
|--------|------|---------|
| Git | ណាក៏បាន | `git --version` |
| Python | 3.10+ (សាកល្បង 3.12) | `python3 --version` (Mac) / `python --version` (Windows) |
| Node.js | 18+ | `node --version` |
| FFmpeg | ណាក៏បាន (ត្រូវនៅក្នុង PATH) | `ffmpeg -version` |

### 2. macOS

```
# ដំឡើងឧបករណ៍ (ត្រូវការ Homebrew: https://brew.sh)
brew install git python node ffmpeg

# Clone
git clone https://github.com/fbsamnang097-ops/kh-drama-studio.git
cd kh-drama-studio

# Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Build frontend
cd frontend && npm install && npm run build && cd ..

# រត់
PYTHONPATH=. python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### 3. Windows (PowerShell)

```
# ដំឡើងឧបករណ៍ (បិទ ហើយបើក PowerShell ឡើងវិញក្រោយដំឡើង)
winget install Git.Git Python.Python.3.12 OpenJS.NodeJS Gyan.FFmpeg

# Clone
git clone https://github.com/fbsamnang097-ops/kh-drama-studio.git
cd kh-drama-studio

# Python environment
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Build frontend
cd frontend; npm install; npm run build; cd ..

# រត់
$env:PYTHONPATH = "."
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

បើ PowerShell ទប់ស្កាត់ការ activate សូមរត់ម្តង៖ `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### 4. បើកប្រើ

បើក http://127.0.0.1:8000 ចុចរូប ⚙️ រួចដាក់ API key (បកប្រែ, STT, TTS)។ Key រក្សាទុកក្នុងម៉ាស៊ីនអ្នកតែប៉ុណ្ណោះ (មិនត្រូវ commit ទៅ GitHub)។

### 5. ធ្វើបច្ចុប្បន្នភាពកូដ (ក្រោយ clone រួច)

ចូលទៅក្នុង folder `kh-drama-studio` រួច activate environment ជាមុន (Mac: `source .venv/bin/activate`, Windows: `.venv\Scripts\Activate.ps1`)៖

```
git pull
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
```

(Windows ប្រើ `;` ជំនួស `&&`: `cd frontend; npm install; npm run build; cd ..`) រួច restart server ហើយ refresh browser ដោយ `Cmd+Shift+R` (Mac) ឬ `Ctrl+Shift+R` (Windows)។

### 6. ដំណោះស្រាយបញ្ហាទូទៅ

| បញ្ហា | ដំណោះស្រាយ |
|-------|-----------|
| `python: command not found` (Mac) | ប្រើ `python3` មុន activate ហើយបន្ទាប់ពី `source .venv/bin/activate` ប្រើ `python` បាន |
| `python` មិនស្គាល់ (Windows) | ប្រើ `py -3 -m venv .venv` ឬដំឡើង Python ម្តងទៀត ហើយ tick "Add to PATH" |
| `ffmpeg: command not found` | ដំឡើង FFmpeg (Mac: `brew install ffmpeg`, Windows: `winget install Gyan.FFmpeg`) រួចបើក terminal ថ្មី |
| `ModuleNotFoundError: backend` | ត្រូវរត់ពី root folder ហើយកំណត់ `PYTHONPATH=.` (Mac) ឬ `$env:PYTHONPATH = "."` (Windows) |
| Port 8000 ត្រូវបានប្រើរួច | ប្តូរទៅ `--port 8001` ហើយបើក http://127.0.0.1:8001 |
| ទំព័រទទេ ឬ UI ចាស់ | រត់ `npm run build` ម្តងទៀត រួច hard refresh |
| Apply Layers / Blur បរាជ័យ | ត្រូវ Export វីដេអូជាមុន ហើយធ្វើក្នុង session តែមួយ |

ចំណាំ៖ ផ្នែក **Web App** ខាងលើមានជំហានដូចគ្នា ហើយផ្នែកនេះបន្ថែមការ update និងដំណោះស្រាយបញ្ហា។

* * *

## ទាញយកកម្មវិធី (មិនបាច់ដំឡើង Python)

ទាញយកពីទំព័រ [Releases](https://github.com/fbsamnang097-ops/kh-drama-studio/releases) — ជ្រើស Release ថ្មីបំផុត៖

| ប្រព័ន្ធ | File ត្រូវទាញយក |
|---------|------------------|
| Windows 10/11 (x64) | `KH-Drama-Studio-vX.Y.Z.exe` (installer) |
| Mac Intel | `KH-Drama-Studio-vX.Y.Z-x64.dmg` |
| Mac Apple Silicon (M1 / M2 / M3 / M4) | `KH-Drama-Studio-vX.Y.Z-arm64.dmg` |

**Windows៖** ទាញយកតែ `.exe` ឈ្មោះមាន version ច្បាស់ (កុំទាញ `.blockmap` ឬ `latest.yml`) → រត់ installer → បើកកម្មវិធីពី Start Menu។ កុំយក exe ចាស់ដែលបានរក្សាទុកក្នុង Downloads ឬ shortcut ចាស់លើ taskbar។ ប្រសិនបើ app ចាស់នៅបើក សូមបិទទាំងអស់ ហើយដំឡើង installer ថ្មីម្ដងទៀត។ ទិន្នន័យគម្រោង/ការកំណត់ស្ថិតនៅ `%APPDATA%\\KHDramaStudio` ហើយការលុប app មិនត្រូវលុប folder នេះទេ។

ដឹងថា Mac ជាប្រភេទណា៖ ម៉ឺនុយ Apple → About This Mac → មើល Chip (Apple M... ឬ Intel)។

**Mac៖** Unzip រួច **right-click លើ file → Open → Open** (ត្រូវធ្វើតែលើកដំបូង)។ បើ Mac និយាយថា file "damaged" ឬមិនបើក សូមរត់ក្នុង Terminal៖ `xattr -dr com.apple.quarantine ~/Downloads/KH-Drama-Studio-mac-arm64` ហើយ `chmod +x ~/Downloads/KH-Drama-Studio-mac-arm64` (ប្តូរឈ្មោះ file តាម Mac របស់អ្នក) រួចរត់ `~/Downloads/KH-Drama-Studio-mac-arm64`។

បើកលើកដំបូងអាចយឺត 5-15 វិនាទី។ ចុចរូប ⚙️ ដើម្បីដាក់ API key (បកប្រែ, STT, TTS)។

**ទិន្នន័យ និង key** ត្រូវរក្សាក្នុង folder ផ្ទាល់ខ្លួនរបស់អ្នកប្រើ មិនមែនក្នុង app ទេ៖ Windows `%APPDATA%\KHDramaStudio`, Mac `~/Library/Application Support/KHDramaStudio`។

**ដែនកំណត់៖** កំណែ app មិនមាន Whisper (local) និង demucs ទេ ដូច្នេះ STT ត្រូវប្រើ Groq / OpenAI តាម API key។ app មិនទាន់ sign ដូច្នេះប្រព័ន្ធអាចព្រមាន។ app មាន FFmpeg (GPL, https://ffmpeg.org) ភ្ជាប់មកជាមួយ។

### ចេញកំណែថ្មី (សម្រាប់អ្នកអភិវឌ្ឍ)

1. ប្តូរលេខក្នុង file `VERSION` **និង** `package.json` (`"version"`) ឱ្យដូចគ្នា (ឧ. `1.0.14`) ហើយ commit
2. `git tag v1.0.14 && git push origin v1.0.14`
3. GitHub Actions (tab Actions → Build apps) នឹង build Windows, Mac Intel, Mac ARM ហើយដាក់ file ក្នុង Releases ដោយស្វ័យប្រវត្តិ

tag ត្រូវដូច `VERSION` និង `package.json` (`v1.0.14` ↔ `1.0.14`) បើមិនដូច្នេះ build នឹងបរាជ័យ។ លេខនេះបង្ហាញក្នុង footer របស់ app ផងដែរ។
