from .utils import open_safe
import json, os, pathlib, asyncio, base64, time, httpx
from xml.sax.saxutils import escape
SF = pathlib.Path(__file__).parent / "settings.json"
def load():
    d = json.loads(SF.read_text()) if SF.exists() else {}
    d.update({k[3:].lower(): v for k, v in os.environ.items() if k.startswith("KH_") and v})   # Render env vars
    return d
def save(d): SF.write_text(json.dumps(d)); os.chmod(SF, 0o600)
def masked(d): return {k: ("••••" + v[-4:] if k.startswith("key_") and v else v) for k, v in d.items()}

# ទី១ក្នុងបញ្ជី = លំនាំដើម។ model/voice អាចកែក្នុង Settings (ឈ្មោះ model ប្តូរញឹកញាប់)
CATALOG = {
  "translate": {
    "codecraft": {"key": True, "model": "claude-opus-4.8"}, "openai": {"key": True, "model": "gpt-4o"},
    "anthropic": {"key": True, "model": "claude-sonnet-5-5"}, "gemini": {"key": True, "model": "gemini-2.5-flash"},
    "groq": {"key": True, "model": "llama-3.3-70b-versatile"}, "deepseek": {"key": True, "model": "deepseek-chat"},
    "openrouter": {"key": True, "model": "anthropic/claude-sonnet-4.5"}, "mistral": {"key": True, "model": "mistral-large-latest"},
    "together": {"key": True, "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo"},
    "google_free": {"key": False},   # Google Translate ឥតគិតថ្លៃ (មិនផ្លូវការ, មានកំណត់)
    "custom": {"key": True, "model": "", "base": True}},
  "stt": {
    "local": {"key": False, "model": "tiny"}, "openai": {"key": True, "model": "whisper-1"},
    "groq": {"key": True, "model": "whisper-large-v3"}, "custom": {"key": True, "model": "whisper-1", "base": True}},
  "tts": {
    "edge": {"key": False, "male": "km-KH-PisethNeural", "female": "km-KH-SreymomNeural"},
    "azure": {"key": True, "region": True, "male": "km-KH-PisethNeural", "female": "km-KH-SreymomNeural"},
    "google": {"key": True, "male": "km-KH-Standard-A", "female": "km-KH-Standard-A"},
    "elevenlabs": {"key": True, "male": "(Voice ID)", "female": "(Voice ID)"},
    "openai": {"key": True, "model": "gpt-4o-mini-tts", "male": "onyx", "female": "nova"},
    "custom": {"key": True, "model": "tts-1", "male": "onyx", "female": "nova", "base": True}},
}
BASES = {"codecraft": "https://codecraftapi.com/v1", "openai": "https://api.openai.com/v1", "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
         "groq": "https://api.groq.com/openai/v1", "deepseek": "https://api.deepseek.com/v1", "openrouter": "https://openrouter.ai/api/v1",
         "mistral": "https://api.mistral.ai/v1", "together": "https://api.together.xyz/v1"}

# ---------- កម្រិតគុណភាព: Standard / Premium ----------
# Standard = លំនាំដើមដើម (ឥតគិតថ្លៃភាគច្រើន) | Premium = សេវាបង់ប្រាក់ គុណភាពខ្ពស់
# កែ provider/model នៅទីនេះ ឬក្នុង Settings (ប្រើ tab Standard / Premium)
TIERS = {
  "standard": {
    "translate": {"provider": "google_free"},
    "stt": {"provider": "local", "model": "tiny"},
    "tts": {"provider": "edge"},
    "export": {"preset": "medium", "crf": 17, "abr": "192k"},
    "context": 0,    # ចំនួនបន្ទាត់មុនៗ ដែលផ្ញើជាបរិបទពេលបកប្រែ
  },
  "premium": {
    "translate": {"provider": "anthropic", "model": "claude-opus-5-5"},
    "stt": {"provider": "openai", "model": "whisper-1"},
    "tts": {"provider": "azure"},
    "export": {"preset": "slow", "crf": 18, "abr": "192k"},
    "context": 6,
  },
}
def tier(cfg): t = cfg.get("tier", "standard"); return t if t in TIERS else "standard"
def _tget(cfg, role, name, suffix=""):
    t = tier(cfg); k = f"{t}_{role}_{name}{suffix}"
    if cfg.get(k): return cfg[k]
    return cfg.get(f"{role}_{name}{suffix}") if t == "standard" else None   # ត្រូវគ្នាជាមួយ settings.json ចាស់
def prov(cfg, role): return _tget(cfg, role, "provider") or TIERS[tier(cfg)][role]["provider"]
def model_for(cfg, role, p):
    d = TIERS[tier(cfg)][role]
    default = d["model"] if d["provider"] == p and d.get("model") else CATALOG[role][p].get("model", "")
    return _tget(cfg, role, "model", f"_{p}") or default
def _g(cfg, k, default=""): return cfg.get(k) or default
def _key(cfg, role, p):
    k = cfg.get(f"key_custom_{role}" if p == "custom" else f"key_{p}")
    if not k: raise KeyError(f"API Key របស់ {p}")
    return k
def _base(cfg, role, p):
    b = cfg.get(f"base_{role}") if p == "custom" else BASES[p]
    if not b: raise KeyError(f"Base URL ({role})")
    return b.rstrip("/")


# ---------- Speech-to-Text ----------
_WM = None
def stt(audio_path, cfg):
    global _WM
    p = prov(cfg, "stt"); model = model_for(cfg, "stt", p)
    if p == "local":   # ឥតគិតថ្លៃ, ទាញ model ម្តងដំបូង
        from faster_whisper import WhisperModel
        if not _WM or _WM[0] != model:
            _WM = None   # free the old model before loading a new one
            _WM = (model, WhisperModel(model, device="cpu", compute_type="int8", cpu_threads=2, num_workers=1))
        segs, _ = _WM[1].transcribe(str(audio_path), language="zh", vad_filter=True)
        return [{"start": s.start, "end": s.end, "zh": s.text.strip()} for s in segs]
    with open_safe(audio_path, "rb") as f:   # OpenAI / Groq / custom (OpenAI-compatible)
        r = httpx.post(f"{_base(cfg, 'stt', 'openai' if p == 'openai' else p)}/audio/transcriptions",
            headers={"Authorization": f"Bearer {_key(cfg, 'stt', p)}"},
            data={"model": model, "language": "zh", "response_format": "verbose_json"}, files={"file": f}, timeout=600)
    r.raise_for_status()
    return [{"start": s["start"], "end": s["end"], "zh": s["text"].strip()} for s in r.json()["segments"]]

# ---------- Translation zh -> km ----------
PROMPT = ("Translate each Chinese line to natural spoken Khmer for drama dubbing. Also guess the speaker: "
          "'男主' (male lead), '女主' (female lead) or '旁白' (narrator). Reply ONLY with a JSON array "
          'of {"km":"...","char":"..."} in the same order and length.\n')
def _chat(cfg, p, msg):
    model = model_for(cfg, "translate", p); key = _key(cfg, "translate", p)
    if p == "anthropic":
        r = httpx.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
            json={"model": model, "max_tokens": 8000, "messages": [{"role": "user", "content": msg}]}, timeout=300)
        r.raise_for_status(); return r.json()["content"][0]["text"]
    r = httpx.post(f"{_base(cfg, 'translate', p)}/chat/completions", headers={"Authorization": f"Bearer {key}"},
        json={"model": model, "messages": [{"role": "user", "content": msg}]}, timeout=300)
    r.raise_for_status(); return r.json()["choices"][0]["message"]["content"]
PREMIUM_NOTE = ("Quality rules: keep character names and terminology consistent, preserve emotion and register "
                "(romantic, angry, formal...), use natural Cambodian drama dialogue, and keep each line short enough "
                "to be spoken within the original timing.\n")
_GF_CACHE = {}
_GF_BLOCK = 0.0   # Google ត្រូវបានបិទរហូតដល់ម៉ោងនេះ (time.time)
_EDGE_TOK = {"t": "", "at": 0.0}
def _google_once(text):
    r = httpx.get("https://translate.googleapis.com/translate_a/single",
        params={"client": "gtx", "sl": "zh-CN", "tl": "km", "dt": "t", "q": text}, timeout=30)
    if r.status_code in (302, 403, 429):
        raise RuntimeError("blocked " + str(r.status_code))
    r.raise_for_status()
    return "".join(seg[0] for seg in r.json()[0] if seg and seg[0])
def _edge_tr(text):
    now = time.time()
    if not _EDGE_TOK["t"] or now - _EDGE_TOK["at"] > 480:
        r = httpx.get("https://edge.microsoft.com/translate/auth", timeout=20, follow_redirects=True)
        r.raise_for_status(); _EDGE_TOK["t"] = r.text.strip(); _EDGE_TOK["at"] = now
    r = httpx.post("https://api-edge.cognitive.microsofttranslator.com/translate",
        params={"from": "zh-Hans", "to": "km", "api-version": "3.0"},
        headers={"Authorization": "Bearer " + _EDGE_TOK["t"], "Content-Type": "application/json"},
        json=[{"Text": text}], timeout=30)
    if r.status_code in (401, 403): _EDGE_TOK["t"] = ""
    r.raise_for_status()
    return r.json()[0]["translations"][0]["text"]
def _mymemory(text):
    import html
    if len(text.encode("utf-8")) > 480: raise RuntimeError("text too long for MyMemory")
    r = httpx.get("https://api.mymemory.translated.net/get", params={"q": text, "langpair": "zh-CN|km"}, timeout=30)
    r.raise_for_status(); j = r.json()
    out = html.unescape((j.get("responseData") or {}).get("translatedText", "") or "")
    if str(j.get("responseStatus")) != "200" or not out.strip() or out.upper().startswith("MYMEMORY WARNING"):
        raise RuntimeError("mymemory status " + str(j.get("responseStatus")))
    return out
def _gfree(text):
    global _GF_BLOCK
    MSG = "[google_blocked] Google Translate ឥតគិតថ្លៃ ត្រូវបានកំណត់ចំនួន ឬបរាជ័យ។ រង់ចាំប្រហែល ១០ នាទី ហើយសាកម្តងទៀត"
    if text in _GF_CACHE: return _GF_CACHE[text]
    if time.time() < _GF_BLOCK: raise RuntimeError(MSG)
    last = None
    for attempt in range(2):
        try:
            out = _google_once(text); _GF_CACHE[text] = out; return out
        except Exception as e:
            last = repr(e)
            print(f"Google free translate failed: {last} | {text[:30]!r}", flush=True)
            if "blocked" in str(e):
                _GF_BLOCK = time.time() + 600; break
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(MSG + " (" + str(last)[:120] + ")")

def translate(lines, cfg):
    p, out, t = prov(cfg, "translate"), [], tier(cfg)
    if p == "google_free":   # បកម្តងមួយបន្ទាត់ · មិនទាយតួអង្គ (រក្សា Character ដែលមានស្រាប់)
        for z in lines:
            out.append({"km": _gfree(z) if z.strip() else ""}); time.sleep(0.4)
        return out
    ctx = TIERS[t]["context"]
    for i in range(0, len(lines), 40):   # ចែកជាបំណែក ដើម្បីកុំឱ្យវែងពេក
        chunk = lines[i:i + 40]; msg = PROMPT + (PREMIUM_NOTE if t == "premium" else "")
        if ctx and i:   # Premium: ផ្ញើបន្ទាត់មុនៗ (ដែលបកហើយ) ជាបរិបទ ដើម្បីឱ្យសម្លេង/ឈ្មោះស្របគ្នា
            prev = [{"zh": z, "km": o.get("km", "")} for z, o in zip(lines[max(0, i - ctx):i], out[max(0, i - ctx):i])]
            msg += ("Context only (previous lines already translated; do NOT include them in your reply):\n"
                    + json.dumps(prev, ensure_ascii=False) + "\nLines to translate:\n")
        t_ = _chat(cfg, p, msg + json.dumps(chunk, ensure_ascii=False))
        got = json.loads(t_[t_.index("["): t_.rindex("]") + 1])
        out += (got + [{}] * len(chunk))[:len(chunk)]
    return out

# ---------- Text-to-Speech (Khmer) ----------
def tts(text, gender, speed, cfg):
    p = prov(cfg, "tts"); c = CATALOG["tts"][p]
    voice = _g(cfg, f"tts_{gender}_{p}", c[gender])
    if p == "edge":   # ឥតគិតថ្លៃ គ្មាន Key
        import edge_tts
        async def go():
            out = bytearray()
            async for ch in edge_tts.Communicate(text, voice, rate=f"{round(speed*100):+d}%").stream():
                if ch["type"] == "audio": out += ch["data"]
            return bytes(out)
        text = " ".join((text or "").split())
        last = None
        for attempt in range(3):
            try:
                data = asyncio.run(go())
                if data: return data
                last = "no audio"
            except Exception as e:
                last = repr(e)
            print(f"Edge TTS attempt {attempt+1} failed: {last} | text={text[:60]!r}", flush=True)
            time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"Edge TTS មិនបានផ្តល់សំឡេង: {text[:40]}")
    key = _key(cfg, "tts", p)
    if p == "azure":
        ssml = f"<speak version='1.0' xml:lang='km-KH'><voice name='{voice}'><prosody rate='{round(speed*100):+d}%'>{escape(text)}</prosody></voice></speak>"
        r = httpx.post(f"https://{_g(cfg,'azure_region','southeastasia')}.tts.speech.microsoft.com/cognitiveservices/v1",
            headers={"Ocp-Apim-Subscription-Key": key, "Content-Type": "application/ssml+xml", "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3"},
            content=ssml.encode(), timeout=120)
    elif p == "google":
        r = httpx.post("https://texttospeech.googleapis.com/v1/text:synthesize", params={"key": key}, timeout=120,
            json={"input": {"text": text}, "voice": {"languageCode": "km-KH", "name": voice},
                  "audioConfig": {"audioEncoding": "MP3", "speakingRate": 1 + speed}})
        r.raise_for_status(); return base64.b64decode(r.json()["audioContent"])
    elif p == "elevenlabs":
        r = httpx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}", headers={"xi-api-key": key}, timeout=120,
            json={"text": text, "model_id": "eleven_multilingual_v2", "voice_settings": {"speed": 1 + speed}})
    else:   # openai / custom: /audio/speech
        r = httpx.post(f"{_base(cfg, 'tts', p) if p == 'custom' else BASES['openai']}/audio/speech",
            headers={"Authorization": f"Bearer {key}"}, timeout=120,
            json={"model": _g(cfg, f"tts_model_{p}", c.get("model", "")), "input": text, "voice": voice, "speed": 1 + speed})
    r.raise_for_status(); return r.content
