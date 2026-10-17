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
