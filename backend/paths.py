"""ទីតាំង file: រត់ធម្មតា = ក្នុង project; ជា exe/app = ទិន្នន័យក្នុង folder អ្នកប្រើ (សរសេរបាន និងមិនបាត់)"""
import os, sys, pathlib

FROZEN = bool(getattr(sys, "frozen", False))
ROOT = pathlib.Path(getattr(sys, "_MEIPASS", pathlib.Path(__file__).parent.parent))

def _data_dir():
    if not FROZEN: return ROOT
    if sys.platform == "win32":
        base = pathlib.Path(os.environ.get("APPDATA") or pathlib.Path.home())
    elif sys.platform == "darwin":
        base = pathlib.Path.home() / "Library" / "Application Support"
    else:
        base = pathlib.Path(os.environ.get("XDG_DATA_HOME") or (pathlib.Path.home() / ".local" / "share"))
    return base / "KHDramaStudio"

# KH_DATA_DIR = ការកំណត់សម្រាប់តេស្ត (ប្រើ folder ដាច់ដោយឡែក) — មិនប៉ះទិន្នន័យពិត
DATA = pathlib.Path(os.environ["KH_DATA_DIR"]) if os.environ.get("KH_DATA_DIR") else _data_dir()
STORE = DATA / "storage"; STORE.mkdir(parents=True, exist_ok=True)
SETTINGS = (DATA / "settings.json") if FROZEN else (ROOT / "backend" / "settings.json")
