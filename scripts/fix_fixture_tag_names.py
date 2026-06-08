"""
One-off script: fix mojibake tag name_bs values in production-galleries.json.

Run from the repo root:
    python scripts/fix_fixture_tag_names.py
"""

import json
import os
import shutil

# slug → correct Bosnian name_bs
REPAIRS = {
    "bjelouska":         "Bjelouška",
    "caplja":            "Čaplja",
    "crni-dazdevnjak":   "Crni daždevnjak",
    "crvendac":          "Crvendać",
    "cuk":               "Ćuk",
    "dazdevnjak":        "Daždevnjak",
    "divlja-macka":      "Divlja mačka",
    "djetlic":           "Djetlić",
    "gusteri":           "Gušteri",
    "jez":               "Jež",
    "krastace":          "Krastače",
    "misar":             "Mišar",
    "mladuncad":         "Mladunčad",
    "nocne-zivotinje":   "Noćne životinje",
    "nocni-snimci":      "Noćni snimci",
    "pcele":             "Pčele",
    "pecina":            "Pećina",
    "puzevi":            "Puževi",
    "rijecne-zivotinje": "Riječne životinje",
    "sismisi":           "Šišmiši",
    "smedi-medvjed":     "Smeđi medvjed",
    "suma":              "Šuma",
    "sumske-zivotinje":  "Šumske životinje",
    "tragovi-zivotinja": "Tragovi životinja",
    "zabe":              "Žabe",
    "zelembac":          "Zelembać",
}

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "production-galleries.json")
FIXTURE = os.path.normpath(FIXTURE)

data = json.load(open(FIXTURE, "r", encoding="utf-8"))

fixed = 0
for record in data:
    if record.get("model") != "gallery.tag":
        continue
    slug = record["fields"].get("slug", "")
    if slug not in REPAIRS:
        continue
    correct = REPAIRS[slug]
    old = record["fields"]["name_bs"]
    if old == correct:
        print(f"  [ok]      {slug!r}  already correct")
        continue
    record["fields"]["name_bs"] = correct
    print(f"  [fixed]   {slug!r}")
    print(f"            was:  {old!r}")
    print(f"            now:  {correct!r}")
    fixed += 1

with open(FIXTURE, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
    f.write("\n")

print(f"\nDone: {fixed} tag name_bs values corrected in {FIXTURE}")
