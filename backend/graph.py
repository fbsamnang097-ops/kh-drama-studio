"""Logo / Sponsor / Overlay / Khmer Text / Blur → គូរក្នុង FFmpeg **pass តែមួយ**

មុននេះ layer និង blur ត្រូវ Apply ម្តងមួយ (Export → _km.mp4 → _km_ly.mp4 → _km_bl.mp4)
ដែលធ្វើឱ្យវីដេអូត្រូវ encode ច្រើនដង និងគុណភាពធ្លាក់។ ឥឡូវ Export ខ្លួនឯងបញ្ចូល
subtitle + សំឡេង + BGM + layer ទាំងអស់ + blur box ក្នុង filter graph តែមួយ។

លំដាប់គូរ (ក្រោម → លើ):  វីដេអូ → Blur → Subtitle → Logo → Sponsor → Overlay → Khmer Text
ដូច្នេះ Blur បាំងតែអ្វីដែលមានក្នុងវីដេអូដើម (មុខ, ស្លាក, អក្សរបរទេស) មិនបាំង
អក្សរខ្មែរ ឬ logo ដែលយើងដាក់ពីលើទេ។
"""
import base64
import pathlib
import subprocess

LAYER_ORDER = ["logo", "sponsor", "overlay", "text"]   # លំដាប់ដាក់ (ក្រោយ = លើគេ)
IMGS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
VIDS = {".mp4", ".mov", ".webm", ".mkv"}


def _num(v):
    return f"{float(v):.3f}"


def _pct(v, d=50.0):
    try:
        f = float(v)
    except (TypeError, ValueError):
        f = d
    return max(0.0, min(100.0, f))


# ---------- ឯកសារ layer ----------

def save_text(store, vid, data_url):
    """Khmer Text (data:image/png;base64,...) → {vid}_ly_text.png ក្នុង storage"""
    if not data_url or "," not in str(data_url):
        return None
    try:
        raw = base64.b64decode(str(data_url).split(",", 1)[1])
    except Exception:
        return None
    if not raw:
        return None
    name = f"{pathlib.Path(str(vid)).name}_ly_text.png"
    (pathlib.Path(store) / name).write_bytes(raw)
    return name


def prepare(store, vid, layers):
    """សរសេរ PNG របស់ Khmer Text ចូល storage (បើ frontend ផ្ញើមកជា data URL)"""
    for L in layers or []:
        if L.get("kind") == "text" and L.get("data"):
            n = save_text(store, vid, L["data"])
            if n:
                L["file"] = n
        L.pop("data", None)   # មិនរក្សា base64 ក្នុង memory បន្ថែម
    return layers or []


def layer_inputs(store, layers):
    """→ [(ffmpeg input args, ឈ្មោះ file, layer)] តែ layer ដែលបើក និងមាន file ពិត"""
    out = []
    for kind in LAYER_ORDER:
        for L in layers or []:
            if L.get("kind") != kind or not L.get("enabled", True):
                continue
            name = pathlib.Path(str(L.get("file") or "").split("?")[0]).name
            low = name.lower()
            if not name or not (pathlib.Path(store) / name).is_file():
                continue
            if low.endswith(".mp4") or low.endswith(".mov") or low.endswith(".webm") or low.endswith(".mkv"):
                args = ["-stream_loop", "-1", "-i", name]
            elif low.endswith(".gif"):
                args = ["-ignore_loop", "0", "-i", name]
            else:
                # រូបនៅស្ងៀម (PNG/JPG/WebP) → loop ១ fps គឺគ្រប់គ្រាន់ និងសន្សំ CPU
                # (format/scale របស់ layer មិនត្រូវគណនាឡើងវិញរាល់ frame ទេ)
                args = ["-loop", "1", "-framerate", "1", "-i", name]
            out.append((args, name, L))
    return out


def probe(store, name, fallback=(1080, 1920)):
    """ទំហំវីដេអូ (px) — បើ ffprobe បរាជ័យ ត្រឡប់ fallback"""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
             "-of", "csv=p=0", str(pathlib.Path(store) / name)],
            capture_output=True, text=True, check=True)
        w, h = [int(float(x)) for x in r.stdout.strip().split(",")[:2]]
        if w > 0 and h > 0:
            return w, h
    except Exception as e:
        print("probe failed:", e, flush=True)
    return fallback


def duration(store, name):
    """រយៈពេលវីដេអូ (វិនាទី) — ត្រូវការសម្រាប់កាត់ BGM ដែល loop គ្មានទីបញ្ចប់"""
    for args in (["-show_entries", "format=duration", "-of", "csv=p=0"],
                 ["-select_streams", "v:0", "-show_entries", "stream=duration", "-of", "csv=p=0"]):
        try:
            r = subprocess.run(["ffprobe", "-v", "error", *args, str(pathlib.Path(store) / name)],
                               capture_output=True, text=True, check=True)
            d = float(r.stdout.strip().splitlines()[0])
            if d > 0:
                return d
        except Exception:
            continue
    return 0.0


# ---------- Blur តាម keyframe ----------

def _interp(kfs, key, lo, hi):
    """expression linear interpolation តាម t (វិនាទី) រវាង keyframe"""
    ks = sorted(kfs, key=lambda k: float(k.get("t", 0)))
    if len(ks) == 1:
        e = _num(ks[0][key])
    else:
        e = _num(ks[-1][key])
        for i in range(len(ks) - 2, -1, -1):
            t0, t1 = float(ks[i].get("t", 0)), float(ks[i + 1].get("t", 0))
            v0, v1 = float(ks[i][key]), float(ks[i + 1][key])
            e = (f"if(lt(t,{_num(t1)}),{_num(v0)}+({_num(v1 - v0)})"
                 f"*clip((t-{_num(t0)})/{_num(max(t1 - t0, 0.001))},0,1),{e})")
    return f"clip({e},{_num(lo)},{_num(hi)})"


def _blur_filters(W, H, boxes, cur):
    """បន្ថែម gblur box លើ label cur → (filters, label ថ្មី)"""
    ch = []
    for i, bx in enumerate(list(boxes or [])[:10]):
        bw = max(16, int(W * _pct(bx.get("w", 20), 20) / 100) // 2 * 2)
        bh = max(16, int(H * _pct(bx.get("h", 15), 15) / 100) // 2 * 2)
        bw, bh = min(bw, max(2, W // 2 * 2)), min(bh, max(2, H // 2 * 2))
        kf = bx.get("kf") or []
        if not bx.get("follow") or not kf:
            kf = [{"t": 0, "x": bx.get("x", 50), "y": bx.get("y", 50)}]
        pk = [{"t": k.get("t", 0),
               "x": _pct(k.get("x", 50)) / 100 * W - bw / 2,
               "y": _pct(k.get("y", 50)) / 100 * H - bh / 2} for k in kf]
        xe = _interp(pk, "x", 0, max(0, W - bw))
        ye = _interp(pk, "y", 0, max(0, H - bh))
        try:
            sg = max(2.0, min(80.0, float(bx.get("strength", 25) or 25)))
        except (TypeError, ValueError):
            sg = 25.0
        try:
            st = max(0.0, float(bx.get("start", 0) or 0))
            en = float(bx.get("end", 9999) or 9999)
        except (TypeError, ValueError):
            st, en = 0.0, 9999.0
        ch.append(f"{cur}split[ba{i}][bb{i}]")
        ch.append(f"[bb{i}]crop={bw}:{bh}:x='{xe}':y='{ye}',gblur=sigma={sg:.1f}[bk{i}]")
        ch.append(f"[ba{i}][bk{i}]overlay=x='{xe}':y='{ye}'"
                  f":enable='between(t,{st:.3f},{en:.3f})'[bv{i}]")
        cur = f"[bv{i}]"
    return ch, cur


# ---------- Filter graph ----------

def video_chain(W, H, layer_items=(), first_idx=1, boxes=(), subs_idx=None, scale=False):
    """បង្កើត filter chain សម្រាប់វីដេអូ → (filters, label ចុងក្រោយ)

    [0:v] → scale (បើ HD) → Blur → Subtitle → Logo → Sponsor → Overlay → Khmer Text
    """
    W, H = int(W), int(H)
    ch, cur = [], "[0:v]"
    if scale and W > 0 and H > 0:
        ch.append(f"[0:v]scale={W}:{H}:flags=lanczos[vsc]")
        cur = "[vsc]"

    blur, cur = _blur_filters(W, H, boxes, cur)
    ch += blur

    if subs_idx is not None:
        if scale and W > 0:
            ch.append(f"[{subs_idx}:v]scale={W}:-2:flags=lanczos[vsb]")
            ch.append(f"{cur}[vsb]overlay=x=0:y=H-h:eof_action=pass[vsub]")
        else:
            ch.append(f"{cur}[{subs_idx}:v]overlay=x=0:y=H-h:eof_action=pass[vsub]")
        cur = "[vsub]"

    for j, (_args, _name, L) in enumerate(layer_items):
        ow = max(2, int(W * max(1.0, _pct(L.get("size", 25), 25)) / 100) // 2 * 2)
        a = _pct(L.get("opacity", 90), 90) / 100
        x = _pct(L.get("x", 50), 50) / 100
        y = _pct(L.get("y", 85), 85) / 100
        ch.append(f"[{first_idx + j}:v]format=rgba,scale={ow}:-2,colorchannelmixer=aa={a:.3f}[ly{j}]")
        ch.append(f"{cur}[ly{j}]overlay=x='(W-w)*{x:.4f}':y='(H-h)*{y:.4f}':shortest=1[vl{j}]")
        cur = f"[vl{j}]"
    return ch, cur


def wm_order(layers):
    """លំដាប់ layer សម្រាប់ UI / logging"""
    return [kind for kind in LAYER_ORDER if any(L.get("kind") == kind for L in layers or [])]


def finish(store, src_name, out_name, layer_items, boxes, ff, audio=True):
    """ដាក់ layer + blur លើវីដេអូដែលមានស្រាប់ (pass តែមួយ) — សម្រាប់ route Apply"""
    W, H = probe(store, src_name)
    ch, label = video_chain(W, H, layer_items, 1, boxes)
    inputs = [a for args, _n, _L in layer_items for a in args]
    return ff("-i", src_name, *inputs, "-filter_complex", ";".join(ch), "-map", label,
              *(["-map", "0:a?"] if audio else []),
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
              "-c:a", "copy", "-movflags", "+faststart", out_name)
