"""បញ្ជីសំឡេង (Voice catalog) — តួអង្គនីមួយៗ → សំឡេងខុសៗគ្នា · ថេរពេញរឿង

⚠️ ដែនកំណត់ពិតរបស់ provider ឥតគិតថ្លៃ (edge-tts)៖
   សំឡេងខ្មែរមានតែ **២** — Piseth (ប្រុស) និង Sreymom (ស្រី)។
   ដូច្នេះ ចាស់ · ក្មេង · ក្មេងប្រុស/ស្រី · តួប្រុស ២ នាក់ ត្រូវបង្កើតដោយលៃតម្រូវ
   rate (ល្បឿន) · pitch (កម្ពស់សំឡេង) · volume (កម្រិត) — នេះជាការប៉ាន់ស្មានជិតបំផុត
   ដែលអាចធ្វើបានដោយមិនប្រើសេវាបង់ប្រាក់។
   បើអ្នកកំណត់ Azure/Google/ElevenLabs (មាន key) អាចដាក់ voice id ពិតក្នុង
   Settings ហើយប្រព័ន្ធនឹងប្រើវាជំនួស (voice book នៅដដែល)។
"""

# id → (gender, age, label, rate, pitch, volume, note)
VOICES = {
    # ---------- ប្រុសពេញវ័យ (៣ សំឡេងខុសគ្នា) ----------
    "male_adult_1": ("male", "adult", "ប្រុស ១ · Piseth", "+0%", "+0Hz", "+0%", ""),
    "male_adult_2": ("male", "adult", "ប្រុស ២ · Piseth ធ្ងន់", "-5%", "-9Hz", "+0%", ""),
    "male_adult_3": ("male", "adult", "ប្រុស ៣ · Piseth ស្រាល", "+4%", "+8Hz", "+0%", ""),
    # ---------- ស្រីពេញវ័យ ----------
    "female_adult_1": ("female", "adult", "ស្រី ១ · Sreymom", "+0%", "+0Hz", "+0%", ""),
    "female_adult_2": ("female", "adult", "ស្រី ២ · Sreymom ទាប", "-4%", "-6Hz", "+0%", ""),
    "female_adult_3": ("female", "adult", "ស្រី ៣ · Sreymom ខ្ពស់", "+3%", "+7Hz", "+0%", ""),
    # ---------- ចាស់ ----------
    "elderly_male_1": ("male", "elderly", "ចាស់ប្រុស ១", "-18%", "-24Hz", "-6%", "voice ក្មេងជាងអាយុបន្តិច"),
    "elderly_male_2": ("male", "elderly", "ចាស់ប្រុស ២", "-22%", "-30Hz", "-8%", "voice ក្មេងជាងអាយុបន្តិច"),
    "elderly_female_1": ("female", "elderly", "ចាស់ស្រី ១", "-16%", "-19Hz", "-6%", "voice ក្មេងជាងអាយុបន្តិច"),
    "elderly_female_2": ("female", "elderly", "ចាស់ស្រី ២", "-20%", "-26Hz", "-8%", "voice ក្មេងជាងអាយុបន្តិច"),
    # ---------- ក្មេង ----------
    "boy_1": ("male", "child", "ក្មេងប្រុស ១", "+12%", "+42Hz", "+4%", ""),
    "boy_2": ("male", "child", "ក្មេងប្រុស ២", "+16%", "+50Hz", "+4%", ""),
    "girl_1": ("female", "child", "ក្មេងស្រី ១", "+10%", "+38Hz", "+4%", ""),
    "girl_2": ("female", "child", "ក្មេងស្រី ២", "+14%", "+46Hz", "+4%", ""),
    # ---------- យុវជន ----------
    "teen_male_1": ("male", "teen", "យុវជន · Piseth", "+7%", "+16Hz", "+1%", ""),
    "teen_female_1": ("female", "teen", "យុវនារី · Sreymom", "+7%", "+14Hz", "+1%", ""),
    # ---------- អ្នកនិទាន ----------
    "narrator_male": ("male", "adult", "អ្នកនិទាន · Piseth", "-7%", "-8Hz", "-2%", ""),
    "narrator_female": ("female", "adult", "អ្នកនិទាន · Sreymom", "-6%", "-6Hz", "-2%", ""),
    # ---------- មិនដឹង ----------
    "unknown_1": ("male", "adult", "មិនដឹង · អព្យាក្រឹត", "-3%", "-3Hz", "-3%", "សំឡេងបម្រុង (មិនទាន់ដឹងតួអង្គ)"),
}

# ជម្រើសសម្រាប់ UI (dropdown ក្នុងប្រអប់ Character)
AGE_LABEL = {"child": "ក្មេង", "teen": "យុវជន", "adult": "ពេញវ័យ", "elderly": "ចាស់", "unknown": "មិនដឹង"}
GENDER_LABEL = {"male": "ប្រុស", "female": "ស្រី", "unknown": "មិនដឹង"}

# លំដាប់ជម្រើសក្នុងវគ្គី (បើមានច្រើននាក់ → ខុសគ្នា)
POOL = {
    ("male", "adult"): ["male_adult_1", "male_adult_2", "male_adult_3"],
    ("female", "adult"): ["female_adult_1", "female_adult_2", "female_adult_3"],
    ("male", "elderly"): ["elderly_male_1", "elderly_male_2"],
    ("female", "elderly"): ["elderly_female_1", "elderly_female_2"],
    ("male", "child"): ["boy_1", "boy_2"],
    ("female", "child"): ["girl_1", "girl_2"],
    ("male", "teen"): ["teen_male_1"],
    ("female", "teen"): ["teen_female_1"],
}


def info(voice_id):
    """voice id → dict សម្រាប់ UI/API"""
    v = VOICES.get(voice_id)
    if not v:
        v = VOICES["unknown_1"]
        voice_id = "unknown_1"
    gender, age, label, rate, pitch, volume, note = v
    return {"id": voice_id, "gender": gender, "age": age, "label": label,
            "rate": rate, "pitch": pitch, "volume": volume, "note": note}


def for_character(gender, age, used=None, preferred=None):
    """ជ្រើស voice ត្រឹមត្រូវតាម ភេទ+អាយុ · ជៀសវាងសំឡេងដែលប្រើហើយ (Test I)"""
    used = set(used or [])
    if preferred and preferred in VOICES:
        return preferred
    gender = gender if gender in ("male", "female") else "male"
    age = age if age in ("child", "teen", "adult", "elderly") else "adult"
    pool = POOL.get((gender, age))
    if not pool:                                  # ឧ. ស្រីចាស់គ្មាន → ប្រើស្រីពេញវ័យ
        pool = POOL.get((gender, "adult")) or POOL[("male", "adult")]
    free = [v for v in pool if v not in used]
    return (free or pool)[0]


def all_for_ui():
    return [info(k) for k in VOICES]
