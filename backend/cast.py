"""Auto-scan តួអង្គ (Character) ពីអត្ថបទចិន — rule based សុទ្ធ · ឥតគិតថ្លៃ · មិនត្រូវការ API key

គ្មាន dropdown · គ្មានការកែដោយដៃចាំបាច់ — ប្រព័ន្ធស្កេនខ្លួនឯង ហើយជ្រើសសំឡេងតាមតួអង្គ៖
  👨 男主 (ប្រុស) · 👩 女主 (ស្រី) · 👴 老男 (ចាស់ប្រុស) · 👵 老女 (ចាស់ស្រី)
  🧒 小孩 (ក្មេង) · 👦 小孩男 (ក្មេងប្រុស) · 📖 旁白 (អ្នកនិទាន)

ដំណើរការ ២ ជំហាន៖
  A. ស្គាល់តួអង្គទាំងអស់មុន (global cast) — ឈ្មោះ + កិរិយាសព្ទ ពេញរឿង → ភេទ/អាយុ
  B. បន្ទាត់ម្តងមួយ — រកអ្នកនិយាយ តាមលំដាប់៖
     ១. `旁白/画外音` → អ្នកនិទាន
     ២. អាយុ/ភេទពីពាក្យបញ្ជាក់ (爷爷/奶奶/小孩 ↔ 哥/姐/他/她)
     ៣. ឈ្មោះ + កិរិយាសព្ទ មុន ឬ ក្រោយសម្រង់ (「...」小明说)
     ៤. សព្វនាម 他/她
     ៥. ឆ្លាស់វេនតាមសន្ទនា (បើមិនដឹង)
     ៦. មិនមែនសម្ដី (ការពិពណ៌នា) → អ្នកនិទាន
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
SHORT = {M: "ប្រុស", F: "ស្រី", OM: "ចាស់", OF: "ចាស់", CH: "ក្មេង", CHM: "ក្មេង", NARR: "និទាន"}
COLORS = {M: "#38bdf8", F: "#f472b6", OM: "#f59e0b", OF: "#fb7185", CH: "#34d399", CHM: "#22d3ee", NARR: "#fbbf24"}

# ---------- វចនានុក្រម ----------
FEMALE = ("姐", "妹", "妈", "娘", "婆", "女", "她", "姑娘", "小姐", "夫人", "太太", "阿姨", "姑", "嫂", "婶", "母",
          "妃", "后", "闺女", "公主", "姑娘", "媳妇", "老婆", "妻子", "丫头")
MALE = ("哥", "弟", "爸", "爹", "叔", "舅", "他", "先生", "少爷", "公子", "兄", "爷们", "汉子", "男", "父",
        "皇上", "将军", "王子", "丈夫", "老公", "儿子")
OLD = ("爷爷", "奶奶", "老人", "老太太", "老头", "老伯", "老爹", "老娘", "老伴", "外公", "外婆", "姥姥", "姥爷",
       "老爷子", "大娘", "大爷", "老者", "老妇人", "阿婆", "阿公", "长者", "婆婆", "祖父", "祖母")
OLD_MALE = ("爷爷", "外公", "姥爷", "老爹", "老头", "老伯", "大爷", "阿公", "老爷子", "公公", "老头子", "祖父")
OLD_FEMALE = ("奶奶", "外婆", "姥姥", "老娘", "老太太", "大娘", "阿婆", "老妇人", "婆婆", "祖母", "老婆子")
CHILD = ("小孩", "孩子", "宝宝", "小朋友", "童", "娃", "小妹妹", "小弟弟", "孙子", "孙女",
         "小丫头", "小鬼", "女孩", "男孩", "小女孩", "小男孩", "丫头", "少年", "儿童", "幼儿")
BOY = ("小男孩", "小弟弟", "孙子", "男孩", "小子", "弟弟", "男孩儿")

# ឈ្មោះចិន → ភេទ (ព្យញ្ជនៈទូទៅ) — ជួយ "小明" មិនចេញសំឡេងស្រី
NAME_MALE = ("明", "刚", "强", "伟", "军", "磊", "涛", "勇", "杰", "鹏", "浩", "宇", "峰", "龙", "辉", "斌",
             "超", "亮", "志", "海", "波", "建国", "建华", "文", "武", "山", "川", "凯", "帅", "阳", "晨", "东", "林")
NAME_FEMALE = ("芳", "娜", "敏", "静", "丽", "艳", "娟", "霞", "燕", "玲", "婷", "雪", "梅", "兰", "琴", "秀",
               "花", "蓉", "薇", "颖", "洁", "琳", "倩", "欣", "怡", "瑶", "琪", "妍", "雨", "月", "莲", "凤", "萍")

NARRATOR_CUES = ("旁白", "画外音", "字幕", "镜头", "(Narrator)", "（旁白）")
# កិរិយាសព្ទនិយាយ
SPEECH = ("说", "说道", "问", "问道", "答", "答道", "回答", "喊", "叫道", "叫", "道", "笑道", "哭着说", "低声说",
          "大声说", "嘟囔", "喃喃", "respond", "replied", "said", "说道", "吼", "骂道")
SAY = "说|说道|问|问道|答|答道|回答|喊|叫道|叫|道|笑|哭|嘟囔|喃喃|低声|大声|吼|骂"
# ឈ្មោះមុនកិរិយាសព្ទ (小明说 / 王大姐怒道)
NAME_VERB = re.compile(r"([\u4e00-\u9fa5]{1,4}?)\s*(?:怒|笑|冷|轻|低|大|急|缓缓|冷冷|轻声)?(?:%s)\s*[道:：，,]?[^\u4e00-\u9fa5]*$" % SAY)
NAME_VERB_ANY = re.compile(r"([\u4e00-\u9fa5]{1,4}?)\s*(?:怒|笑|冷|轻|低|大|急|缓缓|冷冷|轻声)?(?:%s)" % SAY)
QUOTED = re.compile(r"[「『“‘\"]([^」』”\"']{1,300})[」』”\"]")
QUOTED_END = re.compile(r"[」』”\"]")
DASH = re.compile(r"^\s*[—\-]{1,2}\s*")
TIME_ONLY = re.compile(r"^[\s\d:：.,，。、\-—…（）()\[\]]+$")
# តួអង្គពិត (មិនមែនពាក្យធម្មតា) — ការពារ "说" ចាប់ពាក្យខុស
STOP_NAMES = {"他们", "她们", "我们", "你们", "大家", "别人", "自己", "有人", "众人", "所有", "这个", "那个",
              "一个", "什么", "怎么", "这样", "那样", "然后", "但是", "可是", "所以", "如果", "因为"}


def _any(text, words):
    return any(w in text for w in words)


def _gender(text):
    """→ 'male' | 'female' | None (សព្វនាម/ពាក្យបញ្ជាក់)"""
    f, m = _any(text, FEMALE), _any(text, MALE)
    if f and not m:
        return "female"
    if m and not f:
        return "male"
    return None


def _name_gender(name):
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
    if _any(txt, OLD):
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


# ---------- A. ស្គាល់តួអង្គពេញរឿង ----------
def build_cast(lines):
    """ឈ្មោះទាំងអស់ + ភេទ/អាយុ → {name: char} (ឈ្មោះដដែល = តួដដែល)"""
    votes = {}
    for line in lines or []:
        raw = str(line or "")
        for m in NAME_VERB_ANY.finditer(raw):
            name = m.group(1).strip()
            if not name or name in STOP_NAMES or len(name) < 2:
                continue
            # យក ២–៣ តួអក្សរចុងក្រោយ (ឈ្មោះចិន) ដើម្បីកុំឱ្យញាប់ពាក្យផ្សេង
            for cand in (name, name[-2:], name[-3:]) if len(name) > 2 else (name,):
                if len(cand) >= 2 and cand not in STOP_NAMES:
                    votes.setdefault(cand, set()).add(m.group(0))
    names = [n for n in votes if _profile(n)]
    names.sort(key=len, reverse=True)
    keep = []
    for n in names:                      # កុំឱ្យ "太太" ជាប់ក្នុង "老太太"
        if not any(n != k and n in k for k in keep):
            keep.append(n)
    return {n: _profile(n) for n in keep}


# ---------- B. បន្ទាត់ម្តងមួយ ----------
def _dialogue_score(raw, quoted):
    """ពិន្ទុថាបន្ទាត់នេះជា "សម្ដី" ឬ "ការពិពណ៌នា" """
    s = 0
    if quoted:
        s += 4
    if DASH.match(raw):
        s += 3
    if re.search(r"[？！?!]\s*$", raw):
        s += 2
    if _any(raw, ("你", "您", "咱们", "吗", "吧", "呢", "喂", "别", "不要")):
        s += 2
    if _any(raw, ("我", "俺", "我们")):
        s += 1
    if _any(raw, SPEECH):
        s += 2
    if "我" in raw:
        s += 1
    if re.match(r"^[\u4e00-\u9fa5]{1,3}[，,]", raw):      # 妈，…… / 小明，……
        s += 2
    if _any(raw, ("夜", "天", "风", "雨", "房间", "街道", "城市", "村", "门口", "灯光", "背影")):
        s -= 1
    return s


def _name_in(raw, cast):
    """ឈ្មោះតួអង្គដែលស្គាល់ពីរឿង → (char, ឈ្មោះ)"""
    for name, ch in sorted(cast.items(), key=lambda x: -len(x[0])):
        if name in raw:
            return ch, name
    return None, None


VOC_HEAD = re.compile(r"^\s*([\u4e00-\u9fa5]{1,4})\s*[，,、]")
VOC_TAIL = re.compile(r"[，,、]\s*([\u4e00-\u9fa5]{1,4})\s*[。！？!?…]*\s*$")

SELF_OLD = ("爷爷", "奶奶", "老子", "老太婆", "老娘", "你爷爷", "你奶奶")
ADDRESS_OLD = ("爷爷", "奶奶", "外公", "外婆", "姥姥", "姥爷", "老爷子", "老太太")
ADDRESS_PARENT = ("妈", "爸", "妈妈", "爸爸", "娘", "爹")


def _inside_cues(spoken, prev=None, prev2=None):
    """សញ្ញាពីខាងក្នុងសម្រង់ → {char: ពិន្ទុ}"""
    out = {}
    txt = str(spoken or "")
    head = txt.split("，")[0].split(",")[0].split("！")[0][:6]
    vocative_old = _any(head, ADDRESS_OLD)          # "爷爷，……" = ហៅ មិនមែននិយាយពីខ្លួន
    second = _any(txt, ("你", "您"))

    # ក. និយាយពីខ្លួនឯងជាមនុស្សចាស់ ("爷爷不怪你") → អ្នកនិយាយ = ចាស់
    if second and not vocative_old and _any(txt, SELF_OLD):
        if _any(txt, ("奶奶", "外婆", "姥姥")):
            out[OF] = max(out.get(OF, 0), 3.0)
        else:
            out[OM] = max(out.get(OM, 0), 3.0)

    # ខ. ហៅមនុស្សចាស់ ("爷爷，您……") → អ្នកនិយាយ = ក្មេង
    if vocative_old and second:
        out[CHM] = max(out.get(CHM, 0), 2.2)

    # គ. ហៅឪពុកម្តាយ ("妈，我……") → កូន ឬ តួឯក (ពិន្ទុខ្សោយ · ឆ្លាស់វេនជាអ្នកសម្រេច)
    if _any(head, ADDRESS_PARENT) and "我" in txt:
        out[CHM] = max(out.get(CHM, 0), 0.9)
        out[F if prev in (M, OM, CHM) else M] = max(out.get(F if prev in (M, OM, CHM) else M, 0), 0.8)

    # ឃ. ប្រើ "您" (គួរសម) → ក្មេង
    if "您" in txt:
        out[CHM] = max(out.get(CHM, 0), 1.0)
    return out


def detect(line, cast=None, prev=None, prev2=None):
    """បន្ទាត់ចិន ១ → (char, conf 0..1)"""
    raw = str(line or "").strip()
    cast = cast or {}
    if not raw or TIME_ONLY.match(raw):
        return NARR, 1.0

    if _any(raw, NARRATOR_CUES):
        return NARR, 0.95

    q = QUOTED.search(raw)
    quoted = bool(q)
    outside = raw[:q.start()] if q else raw                 # មុនសម្រង់ = អ្នកនិយាយ
    tail = raw[q.end():] if q else ""                        # ក្រោយសម្រង់ (「...」小明说)
    spoken = q.group(1) if q else raw

    # អ្នកដែលត្រូវគេហៅ ("爷爷，……" / "……，妈") — មិនមែនអ្នកនិយាយទេ
    voc = ""
    if not quoted:
        mh, mt = VOC_HEAD.match(raw), VOC_TAIL.search(raw)
        for m2 in (mh, mt):
            if m2:
                w = m2.group(1)
                kin = (_any(w, OLD) or _any(w, CHILD) or _any(w, FEMALE) or _any(w, MALE)
                       or w in cast or (_name_gender(w) and len(w) <= 3))
                if kin and len(w) <= 4:
                    voc = w
        if voc:
            outside = outside.replace(voc, " ")

    # បន្ទាត់ខ្លីបន្ទាប់ពីក្មេង ដែលនិយាយអំពីក្មេង → មនុស្សចាស់សរសើរ ("真是个好孩子。")
    if (not quoted and len(raw) <= 12 and prev in (CH, CHM)
            and _any(raw, ("孩子", "好孩子", "乖", "懂事"))):
        return OM, 0.7

    if _dialogue_score(raw, quoted) < 2:                     # ការពិពណ៌នា → អ្នកនិទាន
        return NARR, 0.9

    score = {}

    def add(ch, w):
        if ch:
            score[ch] = score.get(ch, 0) + w

    # ១. អាយុ/ភេទ ពីផ្នែកអ្នកនិយាយ (មុន/ក្រោយសម្រង់)
    for seg, w in ((outside, 3.0), (tail, 2.5)):
        pr = _profile(seg)
        if pr:
            add(pr, w if pr in (OM, OF, CH, CHM) else w * 0.8)

    # ២. ឈ្មោះ + កិរិយាសព្ទ
    for seg, w in ((outside, 4.0), (tail, 3.5), (raw, 2.0)):
        m = NAME_VERB_ANY.search(seg)
        if m:
            name = m.group(1).strip()
            if name and name not in STOP_NAMES:
                for cand in ((name, name[-2:], name[-3:]) if len(name) > 2 else (name,)):
                    if cand in cast:
                        add(cast[cand], w)
                        break
                else:
                    pr = _profile(name)
                    if pr:
                        add(pr, w * 0.7)

    # ៣. ឈ្មោះតួអង្គដែលស្គាល់
    ch, _n = _name_in(outside or tail, cast)
    if ch:
        add(ch, 3.0)

    # ៤. សព្វនាម
    if "她" in outside and "他" not in outside.replace("她", ""):
        add(F, 2.5)
    elif "他" in outside:
        add(M, 2.5)

    # ៤.៥ អ្នកដែលត្រូវហៅ → អ្នកនិយាយជាតួផ្ទុយ
    if voc:
        vp = _profile(voc) or cast.get(voc)
        if vp in (OM, OF):
            add(CHM, 2.0)                     # ហៅចាស់ → ក្មេង/ចៅនិយាយ
        elif vp in (CH, CHM):
            add(OM, 2.0)                      # ហៅក្មេង → មនុស្សចាស់និយាយ ("孩子……")
        elif vp == F:
            add(M, 2.0)                       # ហៅស្រី → ប្រុសនិយាយ
        elif vp == M:
            add(F, 2.0)                       # ហៅប្រុស → ស្រីនិយាយ
        elif vp:
            add(F if prev in (M, OM, CHM) else M, 1.6)

    # ៥. សញ្ញាពីខាងក្នុងសម្រង់ (self-reference / ហៅ)
    for c2, w in _inside_cues(spoken, prev, prev2).items():
        add(c2, w)

    if score and max(score.values()) >= 2.0:
        best = max(score.items(), key=lambda x: x[1])
        total = sum(score.values()) or 1
        conf = min(0.97, 0.5 + 0.45 * (best[1] / total))
        return best[0], round(conf, 2)

    # ៦. ឆ្លាស់វេន សម្រាប់សន្ទនាដែលមិនដឹងអ្នកនិយាយ
    if prev in (M, OM, CHM):
        return F, 0.6
    if prev in (F, OF, CH):
        return M, 0.6
    if prev in (OM, OF):
        return M, 0.55
    return M, 0.55


def scan(lines, keep=None, **kw):
    """lines: [str] → {items:[{char, conf}], counts, summary, ...}"""
    lines = list(lines or [])
    cast = build_cast(lines)
    items, prev, prev2 = [], None, None
    for i, line in enumerate(lines):
        manual = ""
        if keep and i < len(keep):
            manual = normalize(keep[i])
        if manual and manual in CHARS and manual != NARR:
            items.append({"char": manual, "conf": 1.0, "manual": True})
            prev2, prev = prev, manual
            continue
        c, conf = detect(line, cast, prev, prev2)
        items.append({"char": c, "conf": round(conf, 2)})
        if c != NARR:                  # អ្នកនិទានមិនរាប់ក្នុងវេនសន្ទនា
            prev2, prev = prev, c
    counts = {}
    for it in items:
        counts[it["char"]] = counts.get(it["char"], 0) + 1
    return {
        "items": items,
        "counts": counts,
        "label": {c: LABELS.get(c, c) for c in counts},
        "cast": {n: c for n, c in cast.items()},
        "summary": " · ".join(f"{LABELS.get(c, c)} {n}" for c, n in
                              sorted(counts.items(), key=lambda x: -x[1])),
        "changed": sum(1 for it in items if not it.get("manual")),
        "total": len(items),
    }
