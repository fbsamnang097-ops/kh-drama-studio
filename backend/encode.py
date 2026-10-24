"""ជ្រើស video encoder លឿនបំផុតដែលម៉ាស៊ីននេះពិតជាប្រើបាន (hardware) ហើយ fallback ទៅ libx264

- Mac        → `h264_videotoolbox`
- NVIDIA     → `h264_nvenc`
- Intel QSV  → `h264_qsv`
- AMD (Win)  → `h264_amf`
- គ្មានទេ    → `libx264` (software, ដូចដើម)

ការសាកល្បងធ្វើដោយ encode 0.4 វិនាទីពិត ព្រោះ encoder ខ្លះបង្ហាញក្នុង `-encoders`
តែប្រើមិនបាន (driver មិនមាន, GPU ជាប់រវល់...)។ លទ្ធផល cache ទុកម្តង។
កំណត់ដោយដៃបាន៖ `KH_ENCODER=libx264` ឬ `KH_ENCODER=h264_nvenc`
"""
import functools
import os
import pathlib
import subprocess
import tempfile

# ឈ្មោះ preset ខាងក្នុង (libx264) → preset របស់ encoder នីមួយៗ
NVENC_PRESET = {"ultrafast": "p1", "veryfast": "p2", "faster": "p2", "fast": "p3",
                "medium": "p4", "slow": "p6", "slower": "p7"}
QSV_PRESET = {"ultrafast": "veryfast", "veryfast": "veryfast", "faster": "faster", "fast": "fast",
              "medium": "medium", "slow": "slow"}


def _has(name):
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=25)
        return name in r.stdout
    except Exception:
        return False


def _works(args):
    """សាកល្បង encode ពិត 0.4s → encoder នេះដំណើរការមែនទេ"""
    with tempfile.TemporaryDirectory() as d:
        out = pathlib.Path(d) / "t.mp4"
        try:
            r = subprocess.run(
                ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                 "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=25:duration=0.4",
                 "-pix_fmt", "yuv420p", *args, str(out)],
                capture_output=True, timeout=60)
            return r.returncode == 0 and out.is_file() and out.stat().st_size > 0
        except Exception:
            return False


def _hw_args(name, preset, crf):
    """quality/preset សម្រាប់ encoder នីមួយៗ (គ្មាន crf ដូច x264 → បម្លែងជា scale របស់វា)"""
    if name == "h264_videotoolbox":
        return ["-c:v", name, "-q:v", str(max(30, min(85, int(round(90 - 1.5 * crf))))), "-pix_fmt", "yuv420p"]
    if name == "h264_nvenc":
        return ["-c:v", name, "-preset", NVENC_PRESET.get(preset, "p4"), "-tune", "hq",
                "-rc", "vbr", "-cq", str(crf), "-b:v", "0", "-pix_fmt", "yuv420p"]
    if name == "h264_qsv":
        return ["-c:v", name, "-preset", QSV_PRESET.get(preset, "medium"),
                "-global_quality", str(crf), "-pix_fmt", "yuv420p"]
    if name == "h264_amf":
        return ["-c:v", name, "-quality", "balanced", "-rc", "cqp",
                "-qp_i", str(crf), "-qp_p", str(min(51, crf + 2)), "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p"]


CANDIDATES = ["h264_videotoolbox", "h264_nvenc", "h264_qsv", "h264_amf"]


@functools.lru_cache(maxsize=1)
def best():
    """ឈ្មោះ encoder ដែលល្អបំផុតសម្រាប់ម៉ាស៊ីននេះ (probe តែម្តង)"""
    forced = (os.environ.get("KH_ENCODER") or "").strip()
    if forced:
        if forced in ("x264", "libx264", "off", "0"):
            return "libx264"
        if _has(forced) and _works(_hw_args(forced, "medium", 20)):
            return forced
        return "libx264"
    for name in CANDIDATES:
        if _has(name) and _works(_hw_args(name, "medium", 20)):
            return name
    return "libx264"


def info():
    """សម្រាប់បង្ហាញក្នុង UI"""
    name = best()
    hw = name != "libx264"
    return {"encoder": name, "hardware": hw,
            "label": {"h264_videotoolbox": "⚡ VideoToolbox", "h264_nvenc": "⚡ NVENC",
                      "h264_qsv": "⚡ Quick Sync", "h264_amf": "⚡ AMF"}.get(name, "CPU (x264)")}


def video_args(preset="veryfast", crf=20):
    """➜ ffmpeg args សម្រាប់ encode វីដេអូ (hardware បើមាន, បើអត់ libx264)"""
    return _hw_args(best(), preset, int(crf))
