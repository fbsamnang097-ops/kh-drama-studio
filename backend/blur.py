"""Blur boxes (ថេរ ឬដើរតាម keyframe) លើវីដេអូដែល Export រួច ក្នុង FFmpeg តែមួយដង"""
import pathlib, subprocess
from fastapi import APIRouter, HTTPException

def _num(v): return f"{float(v):.3f}"

def _interp(kfs, key, lo, hi):
    """expression linear interpolation តាម t (វិនាទី) រវាង keyframe"""
    ks = sorted(kfs, key=lambda k: float(k["t"]))
    if len(ks) == 1:
        e = _num(ks[0][key])
    else:
        e = _num(ks[-1][key])
        for i in range(len(ks) - 2, -1, -1):
            t0, t1 = float(ks[i]["t"]), float(ks[i + 1]["t"])
            v0, v1 = float(ks[i][key]), float(ks[i + 1][key])
            e = (f"if(lt(t,{_num(t1)}),{_num(v0)}+({_num(v1 - v0)})*clip((t-{_num(t0)})/{_num(max(t1 - t0, 0.001))},0,1),{e})")
    return f"clip({e},{_num(lo)},{_num(hi)})"

def register(app, STORE, ff, guard):
    r = APIRouter()

    @r.post("/api/blur_apply")
    def blur_apply(b: dict):
        vid = pathlib.Path(str(b.get("id", ""))).name
        src = STORE / f"{vid}_km_ly.mp4"
        if not src.is_file(): src = STORE / f"{vid}_km.mp4"
        if not src.is_file(): raise HTTPException(400, "សូម Export វីដេអូជាមុន")
        boxes = b.get("boxes") or []
        if not boxes: raise HTTPException(400, "គ្មាន Blur box")
        try:
            W, H = [int(x) for x in subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                 "-of", "csv=p=0", str(src)], capture_output=True, text=True, check=True).stdout.strip().split(",")[:2]]
        except Exception:
            W, H = 1080, 1920
        flt, base = [], "[0:v]"
        for i, bx in enumerate(boxes[:10]):
            bw = max(16, int(W * max(1.0, min(100.0, float(bx.get("w", 20)))) / 100) // 2 * 2)
            bh = max(16, int(H * max(1.0, min(100.0, float(bx.get("h", 15)))) / 100) // 2 * 2)
            bw, bh = min(bw, W // 2 * 2), min(bh, H // 2 * 2)
            kf = bx.get("kf") or []
            if not bx.get("follow") or not kf:
                kf = [{"t": 0, "x": bx.get("x", 50), "y": bx.get("y", 50)}]
            pk = [{"t": k["t"], "x": float(k["x"]) / 100 * W - bw / 2, "y": float(k["y"]) / 100 * H - bh / 2} for k in kf]
            xe, ye = _interp(pk, "x", 0, W - bw), _interp(pk, "y", 0, H - bh)
            sg = max(2.0, min(80.0, float(bx.get("strength", 25))))
            st, en = max(0.0, float(bx.get("start", 0))), float(bx.get("end", 9999))
            flt.append(f"{base}split[a{i}][b{i}]")
            flt.append(f"[b{i}]crop={bw}:{bh}:x='{xe}':y='{ye}',gblur=sigma={sg:.1f}[k{i}]")
            flt.append(f"[a{i}][k{i}]overlay=x='{xe}':y='{ye}':enable='between(t,{st:.3f},{en:.3f})'[v{i}]")
            base = f"[v{i}]"
        out = f"{vid}_km_bl.mp4"
        guard(lambda: ff("-i", src.name, "-filter_complex", ";".join(flt), "-map", base, "-map", "0:a?",
                         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                         "-c:a", "copy", "-movflags", "+faststart", out))
        return {"url": f"/files/{out}"}

    before = list(app.router.routes)
    app.include_router(r)
    rt = app.router.routes
    new = [x for x in rt if x not in before]
    for x in new: rt.remove(x)
    rt[0:0] = new   # ដាក់មុន static mount
