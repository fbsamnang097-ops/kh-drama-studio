"""Offline TTS stub — **សម្រាប់តេស្តតែប៉ុណ្ណោះ** (KH_TTS_STUB=1)

បង្កើត mp3 ខ្លីៗដោយ ffmpeg (tone) ដើម្បីឱ្យ pipeline (generate → export) រត់បាន
ដោយគ្មាន internet។ ហ្វ្រេកង់ tone ខុសគ្នាតាម voice profile → អាចផ្ទៀងផ្ទាត់បានថា
បន្ទាត់ផ្សេងៗប្រើសំឡេងខុសគ្នាពិត។
មិនត្រូវប្រើក្នុងការប្រើប្រាស់ពិត — provider ពិត (edge-tts) គឺជាផ្លូវដើម។
"""

import math
import subprocess

BASE = {"male": 120.0, "female": 210.0}


def synth(text, profile, seconds=None):
    """profile: (gender, rate, pitch, volume) → bytes mp3"""
    gender, rate, pitch, _vol = profile

    def num(v):
        try:
            return int(str(v).strip().rstrip("%").rstrip("Hz").replace("+", ""))
        except ValueError:
            return 0

    f0 = BASE.get(gender, 120.0) * (1 + num(pitch) / 400.0) * (1 + num(rate) / 800.0)
    dur = seconds or max(0.25, min(3.0, len(str(text or "")) * 0.02))
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
         "-i", f"sine=frequency={f0:.1f}:duration={dur:.2f},volume=0.25",
         "-ar", "24000", "-ac", "1", "-f", "mp3", "-"],
        capture_output=True)
    return r.stdout or b""
