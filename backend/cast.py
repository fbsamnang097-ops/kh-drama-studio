"""Auto-scan តួអង្គ (Character) ពីអត្ថបទចិន — rule based សុទ្ធ · ឥតគិតថ្លៃ · មិនត្រូវការ API key

ប្រើក្រោយ Transcribe ដើម្បីដឹងថាបន្ទាត់ណាជាសម្ដីរបស់តួអង្គណា → សំឡេងត្រូវនឹងតួអង្គ៖
  👨 男主 (ប្រុស) · 👩 女主 (ស្រី) · 👴 老男 (ចាស់ប្រុស) · 👵 老女 (ចាស់ស្រី)
  🧒 小孩 (ក្មេង) · 👦 小孩男 (ក្មេងប្រុស) · 📖 旁白 (អ្នកនិទាន)

គោលការណ៍រកឃើញ (តាមលំដាប់ទម្ងន់)៖
  1. សម្រង់សម្ដី 「」 “” "" ‘’  → ជាសម្ដីតួអង្គ · បើគ្មានសម្រង់ និងគ្មានកិរិយាសព្ទនិយាយ → អ្នកនិទាន
  2. ឈ្មោះ + កិរិយាសព្ទ (小明说 / 她问道 / 老王答道) → ភេទ/អាយុពីឈ្មោះ
  3. ពាក្យបញ្ជាក់ភេទ (姐/妹/妈/她 ↔ 哥/弟/爸/他)
  4. ពាក្យបញ្ជាក់អាយុ (爷爷/奶奶/老人 ↔ 小孩/宝宝/孩子们)
  5. បើស្គាល់ភេទអត់ → ឆ្លាស់វេន ប្រុស/ស្រី (សន្មតតាមវេនសន្ទនា)
  6. ស្គាល់ឈ្មោះដដែលៗ → រក្សាតួអង្គដូចគ្នាពេញរឿង (តាមឈ្មោះ)
"""

import re

# ---------- តួអង្គ ----------
M, F, OM, OF, CH, CHM, NARR = "男主", "女主", "老男", "老女", "小孩", "小孩男", "旁白"

CHARS = [M, F, OM, OF, CH, CHM, NARR]

LABELS = {
    M: "👨 ប្រុស", F: "👩 ស្រី",
    OM: "👴 ចាស់ប្រុស", OF: "👵 ចាស់ស្រី",
    CH: "🧒 ក្មេង", CHM: "👦 ក្មេងប្រុស",
    NARR: "📖 អ្នកនិទាន",
}
COLORS = {M: "#38bdf8", F: "#f472b6", OM: "#f59e0b", OF: "#fb7185", CH: "#34d399", CHM: "#22d3ee", NARR: "#fbbf24"}

# ---------- វចនានុក្រម ----------
FEMALE = ("姐", "妹", "妈", "娘", "婆", "女", "她", "姑娘", "小姐", "夫人", "太太", "阿姨", "姑", "嫂", "婶", "母", "妃", "后", "妹儿", "闺女")
MALE = ("哥", "弟", "爸", "爹", "叔", "舅", "他", "先生", "少爷", "公子", "兄", "爷们", "汉子", "男", "父", "皇上", "将军", "少爷")
OLD = ("爷爷", "奶奶", "老人", "老太太", "老头", "老伯", "老爹", "老娘", "老伴", "外公", "外婆", "姥姥", "姥爷",
       "老爷子", "大娘", "大爷", "老者", "老妇人", "阿婆", "阿公", "长者", "婆婆", " grandma", "grandpa")
OLD_MALE = ("爷爷", "外公", "姥爷", "老爹", "老头", "老伯", "大爷", "阿公", "老爷子", "父", "公公", "老头子")
OLD_FEMALE = ("奶奶", "外婆", "姥姥", "老娘", "老太太", "大娘", "阿婆", "老妇人", "婆婆", "母", "老婆子")
CHILD = ("小孩", "孩子", "宝宝", "小朋友", "童", "娃", "小妹妹", "小弟弟", "闺女", "儿子", "女儿", "孙子", "孙女",
         "小丫头", "小鬼", "女孩", "男孩", "小女孩", "小男孩", "丫头", "少年")
BOY = ("小男孩", "小弟弟", "儿子", "孙子", "男孩", "小子", "弟弟", "小男孩")

# ឈ្មោះចិន → ភេទ (បើគ្មានពាក្យបញ្ជាក់) · ជួយឱ្យ "小明" មិនចេញសំឡេងស្រី
NAME_MALE = ("明", "刚", "强", "伟", "军", "磊", "涛", "勇", "杰", "鹏", "浩", "宇", "峰", "龙", "辉", "斌",
             "超", "亮", "志", "海", "波", "建国", "建华", "文", "武", "山", "川", "磊", "凯", "帅", "阳", "晨")
NAME_FEMALE = ("芳", "娜", "敏", "静", "丽", "艳", "娟", "霞", "燕", "玲", "婷", "雪", "梅", "兰", "琴", "秀",
               "花", "蓉", "薇", "颖", "洁", "琳", "倩", "欣", "怡", "瑶", "琪", "妍", "雨", "月", "莲", "凤")

NARRATOR_CUES = ("旁白", "画外音", "字幕", "镜头", "(Narrator)", "（旁白）")
# កិរិយាសព្ទនិយាយ (មាន = ជាសម្ដីតួអង្គ)
SPEECH = ("说", "说道", "问", "问道", "答", "答道", "回答", "喊", "叫道", "叫", "道", "笑道", "哭着说", "低声说",
          "大声说", "嘟囔", "喃喃", "respond", "replied", "said")
# កិរិយាសព្ទប្រាប់ថាតួអង្គណានិយាយ (ឈ្មោះនៅមុន)
NAME_VERB = re.compile(
    r"([\u4e00-\u9fa5]{1,4}?)\s*(?:说|说道|问|问道|答|答道|回答|喊|叫道|笑|哭|道|嘟囔|喃喃|低声|大声)\s*[道:：，,]?")
QUOTED = re.compile(r"[「『“‘\"']([^」』”\"']{1,200})[」』”\"']")
QUOTE_ANY = re.compile(r"[「『“‘]")
TIME_ONLY = re.compile(r"^[\s\d:：.,，。、\-—…（）()\[\]]+$")

# ឈ្មោះ → តួអង្គ (ភ្ជាប់ពេញរឿង)
_NAME_MEMO = {}


def _any(text, words):
    return any(w in text for w in words)


def _gender(text):
    """→ 'male' | 'female' | None (ពីឈ្មោះ/សព្វនាម)"""
    f, m = _any(text, FEMALE), _any(text, MALE)
    if f and not m:
        return "female"
    if m and not f:
        return "male"
    return None


def _name_gender(name):
    """ឈ្មោះចិន → ភេទ តាមព្យញ្ជនៈទូទៅនៃឈ្មោះ (小明 → ប្រុស)"""
    n = str(name or "")
    f = any(ch in n for ch in NAME_FEMALE)
    m = any(ch in n for ch in NAME_MALE)
    if f and not m:
        return "female"
    if m and not f:
        return "male"
    return None


def _profile(text):
    """→ តួអង្គតាមអាយុ/ភេទ (ឬ None)"""
    txt = str(text or "")
    if _any(txt, OLD):        # ចាស់៖ កំណត់ភេទពីពាក្យចាស់ខ្លួនឯងមុន (爷爷 → ប្រុស)
        if _any(txt, OLD_FEMALE):
            return OF
        if _any(txt, OLD_MALE):
            return OM
        g = _gender(txt) or _name_gender(txt)
        return OF if g == "female" else OM
    if _any(txt, CHILD):
        if _any(txt, BOY):
            return CHM
        g = _gender(txt) or _name_gender(txt)
        return CH if g == "female" else (CHM if g == "male" else CH)
    g = _gender(txt) or _name_gender(txt)
    if g == "female":
        return F
    if g == "male":
        return M
    return None


def normalize(char):
    """តម្លៃចាស់/free-text (男, 男主角, female, 老爷爷...) → កូដតួអង្គស្តង់ដារ"""
    c = str(char or "").strip()
    if not c:
        return ""
    if c in CHARS:
        return c
    low = c.lower()
    if low in ("male", "m", "man", "男", "男主", "男主角", "boy"):
        return M
    if low in ("female", "f", "woman", "女", "女主", "女主角", "girl"):
        return F
    if "旁白" in c or "narrat" in low or "画外音" in c:
        return NARR
    if _any(c, OLD):
        return OF if _gender(c) == "female" else OM
    if _any(c, CHILD):
        return CH if _gender(c) == "female" else CHM
    g = _gender(c)
    return F if g == "female" else M if g == "male" else c


def _name_map(name):
    """ឈ្មោះដដែលៗ → តួអង្គដូចគ្នាពេញរឿង"""
    if not name:
        return None
    if name in _NAME_MEMO:
        return _NAME_MEMO[name]
    p = _profile(name)
    if p:
        _NAME_MEMO[name] = p
    return p


def detect(line, prev=None, turn=0, use_names=True):
    """បន្ទាត់ចិន ១ → (char, conf 0..1)"""
    raw = str(line or "").strip()
    if not raw or TIME_ONLY.match(raw):
        return NARR, 1.0

    if _any(raw, NARRATOR_CUES):                 # ១. សញ្ញាអ្នកនិទានច្បាស់
        return NARR, 0.95

    quoted = QUOTED.search(raw)
    has_quote = bool(quoted)
    has_verb = _any(raw, SPEECH)
    outside = raw[:quoted.start()] if quoted else raw      # ផ្នែកក្រៅសម្រង់ = អ្នកនិយាយ

    if not has_quote and not has_verb:            # ២. គ្មានសម្ដី → អ្នកនិទាន
        return NARR, 0.9

    # ៣. អាយុ (ចាស់/ក្មេង) — មានអាទិភាព ព្រោះសំឡេងខុសគ្នាខ្លាំង
    p = _profile(outside)
    if p in (OM, OF, CH, CHM):
        return p, 0.9

    # ៤. ឈ្មោះ + កិរិយាសព្ទ → តួអង្គជាក់លាក់ (ឈ្មោះដដែល = តួអង្គដដែល)
    if use_names:
        m = NAME_VERB.search(outside) or NAME_VERB.search(raw)
        if m:
            name = m.group(1)
            p = _name_map(name) or _profile(name)
            if p:
                return p, 0.95

    # ៥. សព្វនាម/ពាក្យបញ្ជាក់ភេទ
    if p in (M, F):
        return p, 0.85

    # ៦. សម្រង់សម្ដីតែគ្មានអ្នកនិយាយ → ឆ្លាស់វេន ប្រុស/ស្រី
    other = F if (prev in (M, OM, CHM, NARR, None)) else M
    return other, 0.6 if has_quote else 0.5


def scan(lines, use_names=True, keep=None):
    """lines: [str] → {items:[{char, conf}], summary, counts, changed}

    keep: [char] តម្លៃដែលអ្នកប្រើកែដោយដៃ → រក្សាទុក (មិនសរសេរជាន់)
    """
    global _NAME_MEMO
    _NAME_MEMO = {}
    items, prev, turn = [], None, 0
    for i, line in enumerate(lines or []):
        manual = normalize((keep or [None] * len(lines))[i]) if keep and i < len(keep) else ""
        if manual and manual in CHARS:
            items.append({"char": manual, "conf": 1.0, "manual": True})
            prev = manual
            continue
        c, conf = detect(line, prev, turn, use_names)
        if c in (M, F):
            turn += 1
        items.append({"char": c, "conf": round(conf, 2)})
        prev = c
    counts = {}
    for it in items:
        counts[it["char"]] = counts.get(it["char"], 0) + 1
    changed = sum(1 for it in items if not it.get("manual"))
    return {
        "items": items,
        "counts": counts,
        "label": {c: LABELS.get(c, c) for c in counts},
        "summary": " · ".join(f"{LABELS.get(c, c)} {n}" for c, n in
                              sorted(counts.items(), key=lambda x: -x[1])),
        "changed": changed,
        "total": len(items),
    }
