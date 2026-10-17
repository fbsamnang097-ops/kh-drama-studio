# KH Drama Studio AI

## តម្រូវការ
Python 3.10+, Node.js 18+, FFmpeg (ត្រូវមានក្នុង PATH; ត្រូវដំឡើង font Noto Sans Khmer សម្រាប់ Export Subtitle)

## ដំណើរការ
    pip install -r backend/requirements.txt
    python run.py        # build frontend ម្តងដំបូង → បើក Server → បើក Browser ស្វ័យប្រវត្តិ

បន្ទាប់មកចុច ⚙ Settings ដើម្បីបញ្ចូល API Key។
Dev mode: `uvicorn backend.main:app --reload` និង `cd frontend && npm run dev`

## កម្រិតគុណភាព (Standard / Premium)
ប្តូរនៅរបារខាងលើ (ជិតប៊ូតុង ⚙ Settings)។ កែ provider/model នៃកម្រិតនីមួយៗបានក្នុង Settings (tab Standard / Premium)។

| | Standard | ★ Premium |
|---|---|---|
| បកប្រែ | codecraft (`claude-opus-4.8`) | Anthropic `claude-opus-5-5` + បរិបទ ៦ បន្ទាត់មុន + ច្បាប់រក្សាឈ្មោះ/អារម្មណ៍ |
| STT (ចិន) | Whisper local (ឥតគិតថ្លៃ) | OpenAI `whisper-1` |
| សំឡេងខ្មែរ | Edge TTS (ឥតគិតថ្លៃ) | Azure TTS |
| Export | លឿន (`veryfast`, CRF 23, 128k) | គុណភាពខ្ពស់ (`slow`, CRF 18, 192k) |

Premium ត្រូវការ API Key (Anthropic, OpenAI, Azure + Region)។ Key ប្រើរួមគ្នាទាំងពីរកម្រិត។ លំនាំដើមនៃកម្រិតនីមួយៗកែបាននៅ `TIERS` ក្នុង `backend/providers.py`។

## Google Translate ឥតគិតថ្លៃ (`google_free`)
ជ្រើសក្នុង Settings → Translate → `google_free` (គ្មាន Key)។ ប្រើ endpoint មិនផ្លូវការរបស់ Google, បកម្តងមួយបន្ទាត់, មានកំណត់ចំនួន request (បើជួប 429 វារង់ចាំហើយសាកម្តងទៀត), មិនទាយតួអង្គ (រក្សា Character ដែលមានស្រាប់), គុណភាពតិចជាង Gemini/Claude។

## Export / Import (STT · Translate · TTS)
ជួរ **STT / Translate / TTS** នៅលើតារាង។ ប៊ូតុង ⬇ Export ដំណើរការបន្ទាប់ពីដំណាក់កាលនោះចប់ (STT: ក្រោយ Transcribe · Translate: ក្រោយបកប្រែ · TTS: ក្រោយ Generate Khmer Audio)។ ⬆ Import ប្រើបានជានិច្ច។

| | Export | Import |
|---|---|---|
| STT (ចិន) | SRT · TXT · JSON | SRT · JSON (ត្រូវមានពេលវេលា) — ជំនួស segments ទាំងអស់ |
| Translate (ខ្មែរ) | SRT · TXT · JSON | SRT · TXT · JSON — ផ្គូផ្គងតាមលំដាប់ (ឬតាមពេលវេលា បើចំនួនមិនស្មើ) |
| TTS (សំឡេងខ្មែរ) | MP3 track (លាយតាមពេលវេលា) · ZIP (ក្លីបនីមួយៗ `001.mp3`…) | ZIP ឬ file សំឡេង — លេខនៅដើមឈ្មោះ file = លំដាប់ segment |

ចំណាំ: Import Translate លុបសំឡេងចាស់របស់ segment នោះ (ព្រោះអត្ថបទប្តូរ)។ Import STT លុបការបកប្រែ និងសំឡេងទាំងអស់។
