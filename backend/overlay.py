"""Custom Overlay (PNG/JPG/WebP/GIF): route ថ្មី ដាក់លើវីដេអូដែល Export រួច"""
import pathlib, subprocess
from fastapi import APIRouter, UploadFile, HTTPException

EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

def register(app, STORE, ff, guard):
    r = APIRouter()

    @r.post("/api/overlay")
    async def overlay_upload(id: str, file: UploadFile):
        ext = pathlib.Path(file.filename or "").suffix.lower()
        if ext not in EXT: raise HTTPException(400, "Overlay ត្រូវជា PNG / JPG / JPEG / WebP / GIF")
        vid = pathlib.Path(id).name
        for old in STORE.glob(f"{vid}_ov.*"): old.unlink(missing_ok=True)
        name = f"{vid}_ov{ext}"
        (STORE / name).write_bytes(await file.read())
        return {"url": f"/files/{name}"}

    @r.post("/api/overlay_apply")
    def overlay_apply(b: dict):
        vid = pathlib.Path(str(b.get("id", ""))).name
        src = STORE / f"{vid}_km.mp4"
        if not src.is_file(): raise HTTPException(400, "សូម Export វីដេអូជាមុន")
        o = b.get("overlay") or {}
        name = pathlib.Path(str(o.get("file") or "").split("?")[0]).name
        if not o.get("enabled") or not name or not (STORE / name).is_file():
            raise HTTPException(400, "Overlay ត្រូវបានបិទ ឬមិនទាន់មាន file")
        g = lambda k, d: max(0.0, min(100.0, float(o.get(k, d))))
        try:
            w = int(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width",
                                    "-of", "csv=p=0", str(src)], capture_output=True, text=True, check=True).stdout.strip().split(",")[0])
        except Exception: w = 1080
        ow = max(2, int(w * max(1.0, g("size", 25)) / 100) // 2 * 2)
        loop = ["-ignore_loop", "0"] if name.lower().endswith(".gif") else ["-loop", "1"]
        out = f"{vid}_km_ov.mp4"
        flt = (f"[1:v]format=rgba,scale={ow}:-2,colorchannelmixer=aa={g('opacity', 90) / 100:.3f}[ovl];"
               f"[0:v][ovl]overlay=x='(W-w)*{g('x', 50) / 100:.4f}':y='(H-h)*{g('y', 85) / 100:.4f}':shortest=1[v]")
        guard(lambda: ff("-i", src.name, *loop, "-i", name, "-filter_complex", flt, "-map", "[v]", "-map", "0:a?",
                         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                         "-c:a", "copy", "-movflags", "+faststart", out))
        return {"url": f"/files/{out}"}

    before = list(app.router.routes)
    app.include_router(r)
    rt = app.router.routes
    new = [x for x in rt if x not in before]   # តែ route ថ្មីរបស់ overlay
    for x in new: rt.remove(x)
    rt[0:0] = new                              # ដាក់មុន static mount
