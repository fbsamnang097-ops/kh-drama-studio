"""Layers (logo / sponsor / overlay / text): ដាក់ច្រើន layer លើវីដេអូដែល Export រួច ក្នុង FFmpeg តែមួយដង"""
import pathlib, subprocess
from fastapi import APIRouter, UploadFile, HTTPException

EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
KINDS = ["logo", "sponsor", "overlay", "text"]   # លំដាប់ដាក់ (ក្រោយ = លើគេ)

def register(app, STORE, ff, guard):
    r = APIRouter()

    @r.post("/api/layer")
    async def layer_upload(id: str, kind: str, file: UploadFile):
        if kind not in KINDS: raise HTTPException(400, "kind មិនត្រឹមត្រូវ")
        ext = ".png" if kind == "text" else pathlib.Path(file.filename or "").suffix.lower()
        if ext not in EXT: raise HTTPException(400, "ត្រូវជា PNG / JPG / JPEG / WebP / GIF")
        vid = pathlib.Path(id).name
        for old in STORE.glob(f"{vid}_ly_{kind}.*"): old.unlink(missing_ok=True)
        name = f"{vid}_ly_{kind}{ext}"
        (STORE / name).write_bytes(await file.read())
        return {"url": f"/files/{name}"}

    @r.post("/api/layers_apply")
    def layers_apply(b: dict):
        vid = pathlib.Path(str(b.get("id", ""))).name
        src = STORE / f"{vid}_km.mp4"
        if not src.is_file(): raise HTTPException(400, "សូម Export វីដេអូជាមុន")
        items = []
        for k in KINDS:
            for L in (b.get("layers") or []):
                if L.get("kind") != k or not L.get("enabled"): continue
                n = pathlib.Path(str(L.get("file") or "").split("?")[0]).name
                if n.startswith(f"{vid}_ly_") and (STORE / n).is_file(): items.append((L, n))
        if not items: raise HTTPException(400, "គ្មាន layer ដែលបានបើក និងមាន file")
        try:
            w = int(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width",
                                    "-of", "csv=p=0", str(src)], capture_output=True, text=True, check=True).stdout.strip().split(",")[0])
        except Exception: w = 1080
        def g(L, k, d): return max(0.0, min(100.0, float(L.get(k, d))))
        inputs, flt, base = [], [], "[0:v]"
        for i, (L, n) in enumerate(items):
            ow = max(2, int(w * max(1.0, g(L, "size", 25)) / 100) // 2 * 2)
            inputs += (["-ignore_loop", "0"] if n.lower().endswith(".gif") else ["-loop", "1"]) + ["-i", n]
            flt.append(f"[{i+1}:v]format=rgba,scale={ow}:-2,colorchannelmixer=aa={g(L, 'opacity', 90) / 100:.3f}[l{i}]")
            flt.append(f"{base}[l{i}]overlay=x='(W-w)*{g(L, 'x', 50) / 100:.4f}':y='(H-h)*{g(L, 'y', 85) / 100:.4f}':shortest=1[v{i}]")
            base = f"[v{i}]"
        out = f"{vid}_km_ly.mp4"
        guard(lambda: ff("-i", src.name, *inputs, "-filter_complex", ";".join(flt), "-map", base, "-map", "0:a?",
                         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                         "-c:a", "copy", "-movflags", "+faststart", out))
        return {"url": f"/files/{out}"}

    before = list(app.router.routes)
    app.include_router(r)
    rt = app.router.routes
    new = [x for x in rt if x not in before]
    for x in new: rt.remove(x)
    rt[0:0] = new   # ដាក់មុន static mount
