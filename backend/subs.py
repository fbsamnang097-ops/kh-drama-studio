"""Subtitle burn-in ដោយមិនប្រើ libass: browser គូរអក្សរជារូប PNG → ffmpeg ដាក់ពីលើវីដេអូ (overlay)។
ដំណើរការលើ ffmpeg គ្រប់ build (មិនត្រូវការ libass / freetype)"""
import base64, io, json, pathlib, re, uuid, zipfile

def write_track(store, vid, segs, blank_b64):
    """segs: [{start,end,png}] → សរសេរ PNG ទៅ storage + ឯកសារ concat; ត្រឡប់ឈ្មោះ .txt"""
    def put(name, b64):
        (pathlib.Path(store) / name).write_bytes(base64.b64decode(b64.split(",", 1)[-1])); return name
    blank = put(f"{vid}_blank.png", blank_b64)
    ev = sorted(((s["start"], s["end"], i) for i, s in enumerate(segs) if s.get("png") and s["end"] > s["start"]), key=lambda e: e[0])
    lines, t = ["ffconcat version 1.0"], 0.0
    for k, (a, b, i) in enumerate(ev):
        if k + 1 < len(ev): b = min(b, ev[k + 1][0])      # មិនឱ្យអក្សរជាន់គ្នា
        if b - a < 0.02: continue
        if a - t > 0.01: lines += [f"file '{blank}'", f"duration {a - t:.3f}"]
        lines += [f"file '{put(f'{vid}_s{i}.png', segs[i]['png'])}'", f"duration {b - a:.3f}"]; t = b
    lines += [f"file '{blank}'", "duration 1", f"file '{blank}'"]   # concat ត្រូវការបន្ទាត់ចុងក្រោយម្តងទៀត
    name = f"{vid}_subs.txt"; (pathlib.Path(store) / name).write_text("\n".join(lines) + "\n", encoding="utf-8"); return name

# ---------- លាយសំឡេងតួ + BGM (ducking) ----------
# ពេលតួនិយាយ → ភ្លេងស្ទើរបាត់; ពេលឈប់និយាយ → ភ្លេង BGM ឡើងមកវិញធម្មតា
BGM_VOLUME = 0.6      # កម្រិតភ្លេងពេលគ្មានអ្នកនិយាយ (0.0 – 1.0)
DUCK_RATIO = 20       # ធំ = ភ្លេងបាត់កាន់តែស្ទើរ (8 = លឺស្រាលៗពេលនិយាយ)
DUCK_THRESHOLD = 0.01 # ទាប = ងាយចាប់សំឡេងតួ
DUCK_ATTACK = 20      # ms ភ្លេងចុះលឿនប៉ុនណា ពេលតួចាប់និយាយ
DUCK_RELEASE = 500    # ms ភ្លេងឡើងមកវិញយឺតប៉ុនណា ក្រោយតួឈប់និយាយ

def _mix(n, bgm_idx, pad=False):
    """លាយក្លីបតួ [a0..a(n-1)] → [voice]; បើមាន BGM → បន្ថយភ្លេងពេលតួនិយាយ (sidechain) → [aout]"""
    flt = ["".join(f"[a{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0[voice]"]
    if bgm_idx is None:
        flt.append("[voice]anull[aout]"); return flt
    flt.append("[voice]" + ("apad," if pad else "") + "asplit=2[v1][v2]")
    flt.append(f"[{bgm_idx}:a]volume={BGM_VOLUME}[bg]")
    flt.append(f"[bg][v2]sidechaincompress=threshold={DUCK_THRESHOLD}:ratio={DUCK_RATIO}"
               f":attack={DUCK_ATTACK}:release={DUCK_RELEASE}[duck]")
    flt.append("[v1][duck]amix=inputs=2:duration=first:normalize=0[aout]")
    return flt

def export_args(src, clips, subs_txt, out, q, bgm=None):
    """ឈ្មោះ file ទាំងអស់ជាឈ្មោះសាមញ្ញ (ដំណើរការក្នុង cwd=storage)
    bgm = ឈ្មោះ file ភ្លេង (ជម្រើស) → លាយជាមួយសំឡេងខ្មែរ ដោយបន្ថយភ្លេងពេលតួនិយាយ"""
    inputs, flt = ["-i", src], []
    for i, s in enumerate(clips):
        inputs += ["-i", pathlib.Path(s["audio"]).name]
        flt.append(f"[{i+1}:a]adelay={int(s['start']*1000)}:all=1[a{i}]")
    nxt, bgm_idx = len(clips) + 1, None
    if bgm:
        inputs += ["-stream_loop", "-1", "-i", pathlib.Path(bgm).name]; bgm_idx = nxt; nxt += 1
    flt += _mix(len(clips), bgm_idx, pad=bool(bgm))
    if subs_txt:   # បញ្ចូលអក្សរក្នុងវីដេអូ
        inputs += ["-f", "concat", "-safe", "0", "-i", subs_txt]
        flt.append(f"[0:v][{nxt}:v]overlay=x=0:y=H-h:eof_action=pass[vout]"); vmap = "[vout]"
        venc = ["-c:v", "libx264", "-preset", q["preset"], "-crf", str(q["crf"]), "-pix_fmt", "yuv420p"]
    else:          # បិទអក្សរ → មិន re-encode វីដេអូ (លឿន)
        vmap, venc = "0:v", ["-c:v", "copy"]
    return [*inputs, "-filter_complex", ";".join(flt), "-map", vmap, "-map", "[aout]", *venc,
            "-c:a", "aac", "-b:a", q["abr"], "-movflags", "+faststart", *(["-shortest"] if bgm else []), out]

# ---------- Export / Import TTS ----------
AUD = {".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac"}

def audio_args(clips, out, q, bgm=None):
    """លាយក្លីបសំឡេងខ្មែរទាំងអស់ តាមពេលវេលា → ឯកសារ MP3 មួយ
    bgm = ឈ្មោះ file ភ្លេង (ជម្រើស) → លាយជាមួយសំឡេងខ្មែរ ដោយបន្ថយភ្លេងពេលតួនិយាយ"""
    inputs, flt = [], []
    for i, s in enumerate(clips):
        inputs += ["-i", pathlib.Path(s["audio"]).name]
        flt.append(f"[{i}:a]adelay={int(s['start']*1000)}:all=1[a{i}]")
    bgm_idx = None
    if bgm:
        inputs += ["-stream_loop", "-1", "-i", pathlib.Path(bgm).name]; bgm_idx = len(clips)
    flt += _mix(len(clips), bgm_idx)
    return [*inputs, "-filter_complex", ";".join(flt), "-map", "[aout]", "-c:a", "libmp3lame", "-b:a", q["abr"], out]

def build_zip(store, clips, out_path):
    """ZIP: 001.mp3, 002.mp3 ... (លេខ = លំដាប់ segment ដើម) + segments.json"""
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for i, s in enumerate(clips):
            src = pathlib.Path(store) / pathlib.Path(s["audio"]).name
            if src.exists(): z.write(src, f"{int(s.get('n', i + 1)):03}{src.suffix}")
        z.writestr("segments.json", json.dumps([{k: s.get(k) for k in ("n", "start", "end", "zh", "km", "char")} for s in clips],ensure_ascii=False, indent=2))

def _keep(store, name, data, pos):
    ext = pathlib.Path(name).suffix.lower()
    if ext not in AUD: return None
    m = re.match(r"\s*(\d+)", pathlib.Path(name).stem)           # លេខនៅដើមឈ្មោះ file = លំដាប់ segment
    fn = f"imp_{uuid.uuid4().hex[:10]}{ext}"; (pathlib.Path(store) / fn).write_bytes(data)
    return {"index": int(m.group(1)) if m else pos, "url": f"/files/{fn}"}

def import_audio(store, files):
    """files: [(filename, bytes)] — file សំឡេង ឬ ZIP → [{index,url}]"""
    out = []
    for name, data in files:
        if name.lower().endswith(".zip"):
            z = zipfile.ZipFile(io.BytesIO(data))               # BadZipFile → caller
            for info in sorted(z.infolist(), key=lambda i: i.filename):
                if info.is_dir() or "__MACOSX" in info.filename or info.file_size > 50_000_000: continue
                r = _keep(store, info.filename, z.read(info), len(out) + 1)
                if r: out.append(r)
        else:
            r = _keep(store, name, data, len(out) + 1)
            if r: out.append(r)
    return out
