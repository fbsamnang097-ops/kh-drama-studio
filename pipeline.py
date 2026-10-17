"""
kh-drama-studio: free pipeline  topic -> script -> images -> Khmer voice -> subtitles -> video

APIs used (all free / free-tier):
  - Gemini API (script + images)      needs GEMINI_API_KEY in .env
  - Pollinations (image fallback)     no key
  - edge-tts (Khmer voice)            no key, unofficial
  - FFmpeg (video assembly)           local, must be installed: brew install ffmpeg

Usage:
    python pipeline.py "រឿងស្នេហាក្នុងភូមិមួយ នៅខេត្តសៀមរាប" --scenes 5
"""
import argparse
import asyncio
import base64
import json
import os
import subprocess
import urllib.parse
from pathlib import Path

import edge_tts
import requests
from dotenv import load_dotenv

load_dotenv()

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL", "")    # empty = auto-detect
IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "")  # empty = auto-detect
VOICE = os.getenv("KH_VOICE", "km-KH-SreymomNeural")  # or km-KH-PisethNeural (male)
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _gemini(model: str, body: dict) -> dict:
    if not GEMINI_KEY:
        raise RuntimeError("GEMINI_API_KEY is missing. Put it in .env")
    r = requests.post(
        GEMINI_URL.format(model=model),
        headers={"x-goog-api-key": GEMINI_KEY, "Content-Type": "application/json"},
        json=body,
        timeout=120,
    )
    if not r.ok:
        # show Google's real explanation instead of a bare status code
        raise RuntimeError(f"Gemini error {r.status_code} for model '{model}': {r.text[:600]}")
    return r.json()


_model_cache: dict[str, str | None] = {}
_cand_cache: dict[str, list[str]] = {}
_bad_image_models: set[str] = set()


def model_candidates(kind: str) -> list[str]:
    """All usable models for this key, best first (so we can try the next one on failure)."""
    resolve_model(kind)
    return _cand_cache.get(kind, [])


def resolve_model(kind: str) -> str | None:
    """Ask Google which models this key can use, then pick a suitable one.
    kind = 'text' or 'image'. Returns None if no image model is available."""
    if kind in _model_cache:
        return _model_cache[kind]
    override = TEXT_MODEL if kind == "text" else IMAGE_MODEL
    if override:
        _model_cache[kind] = override
        return override
    r = requests.get(
        "https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
        headers={"x-goog-api-key": GEMINI_KEY},
        timeout=60,
    )
    r.raise_for_status()
    names = [
        m["name"].removeprefix("models/")
        for m in r.json().get("models", [])
        if "generateContent" in m.get("supportedGenerationMethods", [])
    ]
    skip = ("tts", "live", "audio", "embedding", "thinking", "robotics", "computer", "learn")
    if kind == "image":
        cands = [n for n in names if "image" in n and not any(s in n for s in skip)]
    else:
        cands = [n for n in names if "flash" in n and "image" not in n
                 and not any(s in n for s in skip)]
        cands.sort(key=lambda n: ("preview" in n or "exp" in n, "lite" in n, n))
    _cand_cache[kind] = cands
    choice = cands[0] if cands else None
    print(f"  {kind} models available: {cands[:6]}")
    _model_cache[kind] = choice
    return choice


def generate_script(topic: str, scenes: int) -> list[dict]:
    """Returns [{'narration': <Khmer text>, 'image_prompt': <English prompt>}, ...]"""
    prompt = (
        f"Write a short Khmer drama in exactly {scenes} scenes about: {topic}.\n"
        "Return JSON array only. Each item has:\n"
        '  "narration": 1-3 sentences in Khmer (spoken narration),\n'
        '  "image_prompt": an English visual description of the scene, cinematic, no text in image.'
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    models = [TEXT_MODEL] if TEXT_MODEL else model_candidates("text")
    if not models:
        raise RuntimeError("No Gemini text model is available for this API key.")
    last_err = None
    for model in models[:5]:  # try the next model if one is missing / not allowed
        try:
            print(f"  trying text model: {model}")
            data = _gemini(model, body)
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except RuntimeError as e:
            last_err = e
            print(f"  failed: {e}")
            if "429" in str(e):
                break
    raise last_err


def generate_image(prompt: str, out: Path) -> None:
    """Try Gemini image model first, fall back to Pollinations (no key)."""
    # 1) every Gemini image model this key can see (skip ones that already failed this run)
    models = [IMAGE_MODEL] if IMAGE_MODEL else model_candidates("image")
    for model in models:
        if model in _bad_image_models:
            continue
        try:
            data = _gemini(model, {"contents": [{"parts": [{"text": prompt}]}]})
            for part in data["candidates"][0]["content"]["parts"]:
                inline = part.get("inlineData") or part.get("inline_data")
                if inline:
                    out.write_bytes(base64.b64decode(inline["data"]))
                    print(f"  image from {model}")
                    return
            _bad_image_models.add(model)
        except Exception as e:  # noqa: BLE001
            _bad_image_models.add(model)
            print(f"  image model {model} failed: {str(e)[:160]}")

    # 2) Pollinations (may now require payment / a key)
    try:
        url = (
            "https://image.pollinations.ai/prompt/"
            + urllib.parse.quote(prompt)
            + "?width=1280&height=720&nologo=true"
        )
        r = requests.get(url, timeout=180)
        r.raise_for_status()
        out.write_bytes(r.content)
        print("  image from Pollinations")
        return
    except Exception as e:  # noqa: BLE001
        print(f"  Pollinations failed: {str(e)[:120]}")

    # 3) last resort so the video still gets made: a plain coloured frame (no AI image)
    hue = abs(hash(prompt)) % 0xFFFFFF
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", f"color=c=0x{hue:06x}:s=1280x720", "-frames:v", "1", str(out)],
        check=True,
    )
    print("  WARNING: no image service available - used a plain colour frame")


async def _tts(text: str, out: Path) -> None:
    await edge_tts.Communicate(text, VOICE).save(str(out))


def synthesize_voice(text: str, out: Path) -> None:
    asyncio.run(_tts(text, out))


def audio_duration(path: Path) -> float:
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(res.stdout.strip())


def make_clip(image: Path, audio: Path, out: Path, dur: float) -> None:
    frames = int((dur + 0.5) * 25)
    vf = (
        "[0:v]scale=2560:1440:force_original_aspect_ratio=increase,crop=2560:1440,"
        f"zoompan=z='min(zoom+0.0006,1.15)':d={frames}:s=1280x720:fps=25,format=yuv420p[v]"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(image), "-i", str(audio),
         "-filter_complex", vf, "-map", "[v]", "-map", "1:a",
         "-c:v", "libx264", "-c:a", "aac", "-t", f"{dur + 0.3:.2f}", str(out)],
        check=True,
    )


def srt_time(t: float) -> str:
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02}:{int(m):02}:{int(s):02},{int((s % 1) * 1000):03}"


def write_srt(narrations: list[str], durations: list[float], out: Path) -> None:
    """Subtitles built from the script itself (more accurate for Khmer than speech recognition)."""
    t, lines = 0.0, []
    for i, (text, d) in enumerate(zip(narrations, durations), 1):
        lines += [str(i), f"{srt_time(t)} --> {srt_time(t + d)}", text, ""]
        t += d + 0.3
    out.write_text("\n".join(lines), encoding="utf-8")


def concat(clips: list[Path], out: Path, workdir: Path) -> None:
    listfile = workdir / "clips.txt"
    listfile.write_text("".join(f"file '{c.resolve()}'\n" for c in clips))
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(listfile), "-c", "copy", str(out)],
        check=True,
    )


def run(topic: str, scenes: int, outdir: Path) -> Path:
    work = outdir / "work"
    work.mkdir(parents=True, exist_ok=True)

    print("1/4 Writing script...")
    script = generate_script(topic, scenes)
    (outdir / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")

    clips, durations = [], []
    for i, scene in enumerate(script, 1):
        print(f"2/4 Scene {i}/{len(script)}: image + voice")
        img, aud, clip = work / f"s{i}.png", work / f"s{i}.mp3", work / f"s{i}.mp4"
        generate_image(scene["image_prompt"], img)
        synthesize_voice(scene["narration"], aud)
        dur = audio_duration(aud)
        make_clip(img, aud, clip, dur)
        clips.append(clip)
        durations.append(dur)

    print("3/4 Subtitles...")
    write_srt([s["narration"] for s in script], durations, outdir / "subtitles.srt")

    print("4/4 Joining clips...")
    final = outdir / "final.mp4"
    concat(clips, final, work)
    print(f"Done: {final}")
    return final


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("topic")
    ap.add_argument("--scenes", type=int, default=5)
    ap.add_argument("--out", default="storage/output")
    args = ap.parse_args()
    run(args.topic, args.scenes, Path(args.out))
