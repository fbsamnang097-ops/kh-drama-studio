from .utils import open_safe
import json, os, pathlib, asyncio, base64, time, httpx
from xml.sax.saxutils import escape
from .paths import SETTINGS as SF   # exe: settings ក្នុង folder អ្នកប្រើ
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
# ---------- ការផ្ទៀងផ្ទាត់សំឡេងពិតរបស់ provider ----------
# មិនប្រឌិត voice id ទេ — ត្រូវផ្ទៀងផ្ទាត់ជាមួយ provider ពិត (edge-tts list_voices)
PROVIDER_VOICE = {"male": "km-KH-PisethNeural", "female": "km-KH-SreymomNeural"}
_VCACHE = {"data": None, "ts": 0.0}


def provider_voices(cfg=None, refresh=False, ttl=6 * 3600):
    """រាយសំឡេងខ្មែរពិតដែល provider គាំទ្រ → {provider, voices, verified}"""
    cfg = cfg or load()
    p = prov(cfg, "tts")
    import time as _t
    if not refresh and _VCACHE["data"] and (_t.time() - _VCACHE["ts"] < ttl):
        return _VCACHE["data"]
    out = {"provider": p, "voices": [], "verified": False, "source": "static"}
    if p == "edge":
        try:
            import edge_tts

            async def go():
                return await edge_tts.list_voices()

            allv = asyncio.run(go())
            km = [{"id": v.get("ShortName"), "gender": (v.get("Gender") or "").lower(),
                   "locale": v.get("Locale")} for v in allv
                  if str(v.get("Locale", "")).startswith("km")]
            if km:
                out.update(voices=km, verified=True, source="edge-tts list_voices")
                _VCACHE["data"], _VCACHE["ts"] = out, _t.time()
                return out
        except Exception as e:
            out["error"] = str(e)[:160]
    # fallback: តម្លៃដែលដឹងច្បាស់ (មិន verified — គ្មាន internet)
    if p in ("edge", "azure"):
        out["voices"] = [{"id": "km-KH-PisethNeural", "gender": "male", "locale": "km-KH"},
                         {"id": "km-KH-SreymomNeural", "gender": "female", "locale": "km-KH"}]
    elif p == "google":
        out["voices"] = [{"id": "km-KH-Standard-A", "gender": "female", "locale": "km-KH"}]
    _VCACHE["data"], _VCACHE["ts"] = out, _t.time()
    return out


def voice_support_report(cfg=None):
    """voice profile → provider voice ពិត · បញ្ជីដែនកំណត់ដែលត្រូវបង្ហាញ"""
    cfg = cfg or load()
    pv = provider_voices(cfg)
    ids = {v["id"] for v in pv["voices"]}
    from .voices import VOICES
    missing = [k for k, v in VOICES.items() if PROVIDER_VOICE[v[0]] not in ids] if ids else []
    limits = []
    if pv["provider"] == "edge":
        from .voices import NATURAL
        if NATURAL:
            limits.append("សំឡេងធម្មតា — edge-tts មាន ២ សំឡេងខ្មែរ (Piseth ប្រុស · Sreymom ស្រី) · "
                          "គ្មានកែ pitch/rate (តួអង្គប្រុសទាំងអស់ = Piseth · ស្រីទាំងអស់ = Sreymom)")
        else:
            limits.append("edge-tts មានសំឡេងខ្មែរ ២ ប៉ុណ្ណោះ (Piseth ប្រុស · Sreymom ស្រី) — "
                          "ចាស់/ក្មេង/តួប្រុស ២ នាក់ បង្កើតដោយ rate · pitch · volume")
    if missing:
        limits.append(f"voice id ដែលមិនមានក្នុង provider: {', '.join(missing[:4])}")
    return {"provider": pv["provider"], "verified": pv["verified"], "voices": pv["voices"],
            "map": PROVIDER_VOICE, "missing": missing, "limitations": limits,
            "source": pv.get("source")}


# ---------- តួអង្គ → សំឡេង (ឥតគិតថ្លៃ ជាមួយ edge-tts) ----------
# (gender, rate, pitch, volume) — edge-tts គាំទ្រ rate · pitch · volume ដោយផ្ទាល់
# សំឡេងខ្មែរមានតែ ២ (Piseth ប្រុស · Sreymom ស្រី) → បង្កើត ចាស់/ក្មេង
# ដោយលៃតម្រូវ ល្បឿន · សំឡេង · កម្រិតសំឡេង ឱ្យឮខុសគ្នាច្បាស់តែធម្មជាតិ
CHAR_VOICES = {
    "男主":   ("male",   "+0%",  "+0Hz",  "+0%"),    # 👨 ប្រុស — ធម្មតា
    "女主":   ("female", "+0%",  "+0Hz",  "+0%"),    # 👩 ស្រី — ធម្មតា
    "老男":   ("male",   "-16%", "-22Hz", "-6%"),    # 👴 ចាស់ប្រុស — យឺត · ធ្ងន់ · ស្រាល
    "老女":   ("female", "-15%", "-18Hz", "-6%"),    # 👵 ចាស់ស្រី
    "小孩":   ("female", "+8%",  "+34Hz", "+4%"),    # 🧒 ក្មេងស្រី — លឿន · ខ្ពស់
    "小孩男": ("male",   "+10%", "+42Hz", "+4%"),    # 👦 ក្មេងប្រុស
    "旁白":   ("male",   "-7%",  "-8Hz",  "-2%"),    # 📖 អ្នកនិទាន — ស្ងប់ · ច្បាស់
}
CHAR_DEFAULT = "旁白"

# ពាក្យសម្រាប់ UI
VOICE_LABEL = {
    "男主": "ប្រុស · Piseth", "女主": "ស្រី · Sreymom",
    "老男": "ចាស់ប្រុស · Piseth ↓", "老女": "ចាស់ស្រី · Sreymom ↓",
    "小孩": "ក្មេងស្រី · Sreymom ↑", "小孩男": "ក្មេងប្រុស · Piseth ↑",
    "旁白": "អ្នកនិទាន · Piseth",
}


def voice_profile(key):
    """voice id (male_adult_2 · elderly_female_1 …) ឬ role code (男主/老男…) → ការកំណត់សំឡេង

    របៀបធម្មតា (លំនាំដើម) → rate/pitch/volume = 0 ទាំងអស់
    → សំឡេងពិតរបស់ provider ដូចដើម (Piseth / Sreymom)។
    """
    try:
        from .voices import VOICES, NATURAL
        v = VOICES.get(key)
        if v:
            gender, _age, _label, rate, pitch, volume, _note = v
            if NATURAL:
                return (gender, "+0%", "+0Hz", "+0%"), key
            return (gender, rate, pitch, volume), key
    except Exception:
        pass
    return char_profile(key)


def char_profile(char):
    """តួអង្គ → ((gender, rate, pitch, volume), char) ជាមួយ normalize"""
    try:
        from .cast import normalize as _norm
    except ImportError:
        def _norm(x): return x
    c = _norm(char) or CHAR_DEFAULT
    prof = CHAR_VOICES.get(c, CHAR_VOICES[CHAR_DEFAULT])
    try:
        from .voices import NATURAL
        if NATURAL:                       # សំឡេងពិត — គ្មានកែ
            prof = (prof[0], "+0%", "+0Hz", "+0%")
    except Exception:
        pass
    return prof, c


def _num(v):
    try:
        return int(float(str(v).strip().rstrip("%").rstrip("Hz").replace("+", "")))
    except ValueError:
        return 0


def _add_rate(base, extra):
    """'+0%' + speed → '+10%'"""
    return f"{_num(base) + int(round(extra * 100)):+d}%"


def _shift(val, delta, unit):
    return f"{_num(val) + delta:+d}{unit}"


def natural_text(text):
    """សម្អាតអត្ថបទខ្មែរ ឱ្យ TTS អានធម្មជាតិ (ចន្លោះ · សញ្ញា · ចុងប្រយោគ)"""
    t = " ".join(str(text or "").split())
    for a, b in (("，", ", "), ("、", ", "), ("。", "។ "), ("；", "; "), ("：", ": "),
                 ("！", "!"), ("？", "?"), ("「", ""), ("」", ""), ("『", ""), ("』", ""),
                 ("“", ""), ("”", ""), ("……", "…"), ("--", "…")):
        t = t.replace(a, b)
    t = " ".join(t.split())
    t = t.replace(" ,", ",").replace(" .", ".").replace("… ", "… ")
    if t and t[-1] not in ".!?។…":
        t += "។"
    return t


def prosody(text, rate, pitch, volume, seed=0):
    """លៃតម្រូវតាមអត្ថន័យបន្ទាត់ → ស្តាប់ធម្មជាតិ (មិនមែនម៉ាស៊ីន)"""
    t = str(text or "")
    r, p_, v = _num(rate), _num(pitch), _num(volume)
    if t.rstrip().endswith(("!", "！")):
        r, p_ = r + 3, p_ + 5            # រំភើប / ស្រែក
    elif t.rstrip().endswith(("?", "？")):
        r, p_ = r - 2, p_ + 7            # សំណួរ → សំឡេងងើប
    if "…" in t or "......" in t:
        r -= 5                            # ផ្អាក / អក្សរស្ទាក់
    n = len(t)
    if n <= 6:
        r += 2                            # បន្ទាត់ខ្លី → មិនរត់
    elif n > 40:
        r -= 2                            # បន្ទាត់វែង → មិនញាប់
    r += (seed % 5) - 2                   # ±2% ប្រែប្រួលតិចៗ (កុំឱ្យរាបស្មើ)
    r = max(-45, min(45, r))
    p_ = max(-45, min(45, p_))
    return f"{r:+d}%", f"{p_:+d}Hz", f"{v:+d}%"


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
    "export": {"preset": "veryfast", "crf": 20, "abr": "192k"},
    "context": 0,    # ចំនួនបន្ទាត់មុនៗ ដែលផ្ញើជាបរិបទពេលបកប្រែ
  },
  "premium": {
    "translate": {"provider": "anthropic", "model": "claude-opus-5-5"},
    "stt": {"provider": "openai", "model": "whisper-1"},
    "tts": {"provider": "azure"},
    "export": {"preset": "medium", "crf": 19, "abr": "192k"},
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
PROMPT = ("Translate each Chinese line to natural spoken Khmer for drama dubbing. Also guess the speaker and pick "
          "EXACTLY one of these codes: '男主' (adult male), '女主' (adult female), '老男' (old man), "
          "'老女' (old woman), '小孩' (child), '小孩男' (boy child), '旁白' (narrator / no dialogue). "
          "Use the name or pronoun before the speech verb (他说/她说/爷爷/奶奶/小孩). Narrator lines are "
          "description with no quoted speech. Reply ONLY with a JSON array "
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
        for g in got:   # តួអង្គពី AI → កូដស្តង់ដារ (មិនឱ្យសំឡេងខុស)
            if isinstance(g, dict) and g.get("char"):
                try:
                    from .cast import normalize as _norm
                    g["char"] = _norm(g["char"])
                except ImportError:
                    pass
        out += (got + [{}] * len(chunk))[:len(chunk)]
    return out

# ---------- Text-to-Speech (Khmer) ----------
def tts(text, char, speed, cfg):
    """char = តួអង្គ (男主/女主/老男/老女/小孩/小孩男/旁白) ឬ 'male'/'female' ចាស់"""
    p = prov(cfg, "tts"); c = CATALOG["tts"][p]
    (gender, rate, pitch, volume), _char = voice_profile(char)
    voice = _g(cfg, f"tts_{gender}_{p}", c[gender])
    text = natural_text(text)          # សម្អាតអត្ថបទគ្រប់ provider
    if os.environ.get("KH_TTS_STUB") == "1":       # តេស្ត offline (មិនប្រើក្នុង app ពិត)
        from .tts_stub import synth
        return synth(text, (gender, rate, pitch, volume))
    if p == "edge":   # ឥតគិតថ្លៃ គ្មាន Key
        import edge_tts
        rate, pitch, volume = prosody(text, _add_rate(rate, speed), pitch, volume,
                                      seed=sum(map(ord, text[:24])))
        async def go():
            out = bytearray()
            async for ch in edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, volume=volume).stream():
                if ch["type"] == "audio": out += ch["data"]
            return bytes(out)
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
        ssml = (f"<speak version='1.0' xml:lang='km-KH'><voice name='{voice}'>"
                f"<prosody rate='{_add_rate(rate, speed)}' pitch='{pitch}'>{escape(text)}</prosody></voice></speak>")
        r = httpx.post(f"https://{_g(cfg,'azure_region','southeastasia')}.tts.speech.microsoft.com/cognitiveservices/v1",
            headers={"Ocp-Apim-Subscription-Key": key, "Content-Type": "application/ssml+xml", "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3"},
            content=ssml.encode(), timeout=120)
    elif p == "google":
        r = httpx.post("https://texttospeech.googleapis.com/v1/text:synthesize", params={"key": key}, timeout=120,
            json={"input": {"text": text}, "voice": {"languageCode": "km-KH", "name": voice},
                  "audioConfig": {"audioEncoding": "MP3", "speakingRate": 1 + speed,
                                  "pitch": max(-20.0, min(20.0, float(str(pitch).rstrip("Hz") or 0) / 7.0))}})
        r.raise_for_status(); return base64.b64decode(r.json()["audioContent"])
    elif p == "elevenlabs":
        r = httpx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}", headers={"xi-api-key": key}, timeout=120,
            json={"text": text, "model_id": "eleven_multilingual_v2", "voice_settings": {"speed": 1 + speed}})
    else:   # openai / custom: /audio/speech
        r = httpx.post(f"{_base(cfg, 'tts', p) if p == 'custom' else BASES['openai']}/audio/speech",
            headers={"Authorization": f"Bearer {key}"}, timeout=120,
            json={"model": _g(cfg, f"tts_model_{p}", c.get("model", "")), "input": text, "voice": voice, "speed": 1 + speed})
    r.raise_for_status(); return r.content
