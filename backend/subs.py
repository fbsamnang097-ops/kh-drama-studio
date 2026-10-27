"""Subtitle burn-in ដោយមិនប្រើ libass: browser គូរអក្សរជារូប PNG → ffmpeg ដាក់ពីលើវីដេអូ (overlay)។
ដំណើរការលើ ffmpeg គ្រប់ build (មិនត្រូវការ libass / freetype)"""
import base64, io, json, pathlib, re, subprocess, uuid, zipfile

try:
    from . import graph as G
except ImportError:   # ពេលរត់ឯកសារនេះដោយផ្ទាល់
    import graph as G

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
BGM_VOLUME = 0.7      # កម្រិតភ្លេងពេលគ្មានអ្នកនិយាយ (0.0 – 1.0)
DUCK_RATIO = 4        # ធំ = ភ្លេងបាត់កាន់តែខ្លាំង
DUCK_THRESHOLD = 0.05 # ទាប = ងាយចាប់សំឡេងតួ
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

MAX_VOICE_SPEED = 1.15


def _probe_audio_duration(path):
    """រករយៈពេល audio ពិត ដើម្បីកុំឱ្យ clip មុនលេងជាន់ clip បន្ទាប់។"""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        duration = float(r.stdout.strip()) if r.returncode == 0 else 0.0
        return duration if duration > 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def schedule_voice_clips(clips, audio_store=None, duration_probe=None):
    """រៀប clip សំឡេងមិនឱ្យជាន់គ្នា; បង្កើនល្បឿនតិចៗប៉ុណ្ណោះពេលអាចសម។

    បើការកាត់បន្ថយរយៈពេលត្រូវការល្បឿនលើស MAX_VOICE_SPEED នោះរក្សាសំឡេងធម្មជាតិ
    ហើយរំកិល clip បន្ទាប់ទៅក្រោយ ដើម្បីមិនកាត់ពាក្យ និងមិនលាយសំឡេងជាន់គ្នា។
    """
    probe = duration_probe or _probe_audio_duration
    ordered = sorted(enumerate(clips), key=lambda row: (float(row[1].get("start", 0) or 0), row[0]))
    scheduled, previous_end = [], 0.0
    for pos, (original_index, clip) in enumerate(ordered):
        start = max(0.0, float(clip.get("start", 0) or 0))
        audio_path = pathlib.Path(audio_store) / pathlib.Path(clip["audio"]).name if audio_store else pathlib.Path(clip["audio"])
        source_duration = probe(audio_path)
        if not source_duration:
            source_duration = max(0.0, float(clip.get("end", start) or start) - start)
        scheduled_start = max(start, previous_end)
        tempo, trim = 1.0, None
        if pos + 1 < len(ordered):
            next_start = max(0.0, float(ordered[pos + 1][1].get("start", 0) or 0))
            available = next_start - scheduled_start
            target = available - 0.03  # ចន្លោះតូចការពារការជាន់គ្នាពី rounding របស់ codec
            if target > 0 and source_duration > target:
                factor = source_duration / target
                if factor <= MAX_VOICE_SPEED:
                    tempo, trim = factor, target
        output_duration = trim if trim is not None else source_duration
        item = {**clip, "start": scheduled_start, "_tempo": tempo, "_trim": trim,
                "_original_index": original_index}
        scheduled.append(item)
        previous_end = scheduled_start + output_duration
    return scheduled


def _voice_filter(input_index, clip, output_index):
    """Filter clip មួយទៅ timestamp របស់វា និងអនុវត្ត tempo/trim តាម schedule។"""
    chain = f"[{input_index}:a]asetpts=PTS-STARTPTS"
    if clip.get("_tempo", 1.0) > 1.001:
        chain += f",atempo={clip['_tempo']:.6f},atrim=duration={clip['_trim']:.3f}"
    return f"{chain},adelay={int(clip['start'] * 1000)}:all=1[a{output_index}]"


def export_args(src, clips, subs_txt, out, q, bgm=None, layers=(), boxes=(), W=0, H=0, dur=0.0, venc=None, audio_store=None):
    """Export តែមួយ pass: សំឡេងខ្មែរ + BGM + Subtitle + Logo/Sponsor/Overlay/Text + Blur

    q["hd"] = re-encode ច្បាស់; q["tw"],q["th"] = ទំហំ upscale (ស្គាល់ស្វ័យប្រវត្តិពីប្រភព)
    layers = graph.layer_inputs(...) → [(input args, ឈ្មោះ file, layer)]
    boxes  = blur box របស់ BlurPanel;  W,H = ទំហំវីដេអូដើម (px)
    venc   = encoder args ពី `encode.video_args()` (hardware បើមាន); None = libx264
    """
    clips = schedule_voice_clips(clips, audio_store)
    inputs, flt = ["-i", src], []
    for i, s in enumerate(clips):
        inputs += ["-i", pathlib.Path(s["audio"]).name]
        flt.append(_voice_filter(i + 1, s, i))
    nxt, bgm_idx = len(clips) + 1, None
    if bgm:
        inputs += ["-stream_loop", "-1", "-i", pathlib.Path(bgm).name]; bgm_idx = nxt; nxt += 1
    flt += _mix(len(clips), bgm_idx, pad=bool(bgm))

    # ---- វីដេអូ: layer និង subtitle ជា input បន្ថែម ----
    first_layer = nxt
    for args, _name, _L in layers:
        inputs += args; nxt += 1
    subs_idx = None
    if subs_txt:
        inputs += ["-f", "concat", "-safe", "0", "-i", subs_txt]; subs_idx = nxt; nxt += 1

    x264 = venc or ["-c:v", "libx264", "-preset", q["preset"], "-crf", str(q["crf"]), "-pix_fmt", "yuv420p"]
    up = bool(q.get("tw") and q.get("th"))
    vfx = up or bool(layers) or subs_idx is not None or bool(boxes)
    if vfx or q.get("hd"):
        TW, TH = (q["tw"], q["th"]) if up else (W or 1080, H or 1920)
        chain, label = G.video_chain(TW, TH, layers, first_layer, boxes, subs_idx, scale=up)
        flt += chain
        vmap, venc = (label if chain else "0:v"), x264
    else:
        vmap, venc = "0:v", ["-c:v", "copy"]
    # BGM loop គ្មានទីបញ្ចប់ + apad → stream សំឡេងមិនចប់។ `-shortest` មិនកាត់ filter graph
    # បានទេ (ffmpeg រង់ចាំរហូត) ដូច្នេះត្រូវកាត់ដោយ `-t <រយៈពេលវីដេអូ>`។
    cut = ["-t", f"{float(dur):.3f}"] if (bgm and dur and dur > 0) else (["-shortest"] if bgm else [])
    return [*inputs, "-filter_complex", ";".join(flt), "-map", vmap, "-map", "[aout]", *venc,
            "-c:a", "aac", "-b:a", q["abr"], "-movflags", "+faststart", *cut, out]

# ---------- Export / Import TTS ----------
AUD = {".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac"}

def audio_args(clips, out, q, bgm=None, audio_store=None):
    """លាយក្លីបសំឡេងខ្មែរទាំងអស់ តាមពេលវេលា → ឯកសារ MP3 មួយ
    bgm = ឈ្មោះ file ភ្លេង (ជម្រើស) → លាយជាមួយសំឡេងខ្មែរ ដោយបន្ថយភ្លេងពេលតួនិយាយ"""
    clips = schedule_voice_clips(clips, audio_store)
    inputs, flt = [], []
    for i, s in enumerate(clips):
        inputs += ["-i", pathlib.Path(s["audio"]).name]
        flt.append(_voice_filter(i, s, i))
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
