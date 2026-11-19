"""Build lexicon.json from the respellings in names/*.txt.

Each names file has lines `Name | respelling`, for example
`Arrayanes | ah-rye-AH-ness`. Syllables are split by hyphens and the
stressed one is in capitals. This converts each respelling to the phoneme
alphabet Kokoro's British voices use, word by word.

names/overrides.json holds hand-written phonemes that win over the
converter. SKIP lists names the engine already says acceptably.

Usage: python lexicon_build.py [--show] [--tour NAME]

With --tour NAME it reads NAME/names/*.txt and NAME/names/overrides.json,
keeps the Spanish particles from the root names/overrides.json, and writes
NAME/lexicon.json. A combined tour in TOURS (madrid) builds the lexicon of
each of its parts (prado/, reina/); render.py merges them.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SKIP = {
    "Alhambra", "Granada", "Seville", "Madrid", "Mecca", "Gibraltar", "Valencia",
    "Aragon", "Castile", "Castilian", "Fez", "Medina", "Muhammad", "Nasrid",
    "Nasrids", "Qur'an", "San", "Francisco", "Santa", "Sierra", "Nevada",
    "Morocco", "Tunis", "Toledo", "Portugal", "Samuel", "Joseph", "Isabella",
    "Ferdinand", "Charles", "Peter", "Catherine", "Irving", "Washington",
    "Columbus", "Escher", "Islam", "Islamic", "sultan", "sultana", "vizier",
    "emir", "Allah", "Renaissance", "Moorish",
    # Madrid tours
    "Prado", "Picasso", "Spain", "Spanish", "Madrid", "Paris", "Rome",
    "Italy", "Italian", "Flemish", "Baroque", "Napoleon", "Franco",
}
# Combined tours: keep in step with TOURS in render.py.
TOURS = {"madrid": ["prado", "reina"], "toledo": ["toledo_intro", "toledo_dark", "toledo_cathedral", "toledo_sights", "toledo_legends"]}
# Root overrides that every tour shares (Spanish particles and common names).
SHARED = {"de", "del", "la", "los", "las", "Dos", "Juan", "Rey", "Reyes"}

# Longest match first. Vowel patterns carry a leading "V" tag.
RULES = [
    ("eye", "VI"), ("igh", "VI"), ("aow", "VW"), ("air", "Vɛə"), ("eer", "Vɪə"),
    ("oor", "Vʊə"), ("ehr", "Vɛə"), ("ohr", "Vɔː"), ("awl", "Vɔːl"),
    ("ole", "VQl"), ("ah", "Vɑː"), ("eh", "Vɛ"), ("ee", "Viː"), ("oo", "Vuː"),
    ("oh", "VQ"), ("uh", "Və"), ("ay", "VA"), ("ey", "VA"), ("ow", "VW"),
    ("oy", "VY"), ("aw", "Vɔː"), ("ar", "Vɑː"), ("or", "Vɔː"), ("er", "Vɜː"),
    ("ur", "Vɜː"), ("ye", "VI"),
    ("th", "θ"), ("sh", "ʃ"), ("ch", "ʧ"), ("kh", "k"), ("gh", "ɡ"), ("ck", "k"),
    ("ss", "s"), ("ll", "l"), ("rr", "ɹ"), ("zz", "z"), ("nn", "n"), ("mm", "m"),
    ("tt", "t"), ("dd", "d"), ("hw", "w"),
    ("a", "Va"), ("e", "Vɛ"), ("i", "Vɪ"), ("o", "Vɒ"), ("u", "Vʊ"),
    ("j", "ʤ"), ("g", "ɡ"), ("r", "ɹ"), ("c", "k"), ("q", "k"), ("x", "ks"),
]
VOWEL_START = "aeiou"


def syllable(s, stressed):
    out, i, marked = "", 0, False
    low = s.lower()
    while i < len(low):
        if low[i] == "y":
            nxt = low[i + 1] if i + 1 < len(low) else ""
            if nxt and nxt in VOWEL_START and not low.startswith("ye", i) or low.startswith(("yeh", "yee"), i):
                out += "j"
                i += 1
                continue
            if i > 0 and not low.startswith("ye", i):
                ph = "VI"
                i += 1
            else:
                ph = None
        else:
            ph = None
        if ph is None:
            for pat, rep in RULES:
                if low.startswith(pat, i):
                    ph, i = rep, i + len(pat)
                    break
            else:
                ph, i = (low[i] if low[i].isalpha() else ""), i + 1
        if ph.startswith("V"):
            ph = ph[1:]
            if not stressed and ph in ("ʊ", "ɜː"):
                ph = "ə"
            if stressed and not marked:
                ph, marked = "ˈ" + ph, True
        out += ph
    if not any(c in out for c in "aɛɪɒʊəɑiuɔɜAIWQY"):
        out = "ə" + out if out in ("n", "l", "m") else out
    return out


def word(resp):
    syls = [s for s in resp.split("-") if s]
    return "".join(syllable(s, s.isupper() and any(c.isalpha() for c in s)) for s in syls)


def tour_arg():
    if "--tour" in sys.argv:
        return sys.argv[sys.argv.index("--tour") + 1]
    return None


def build(tour=None):
    base = ROOT / tour if tour else ROOT
    lex = {}
    for f in sorted((base / "names").glob("*.txt")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if "|" not in line:
                continue
            name, resp = (x.strip() for x in line.split("|", 1))
            resp = re.sub(r"\(.*?\)", "", resp).strip().replace("'", "")
            names, resps = name.split(), resp.split()
            pairs = zip(names, resps) if len(names) == len(resps) else [(name, resp)]
            for n, r in pairs:
                n = n.strip(",.")
                if n in SKIP or n in lex or not r:
                    continue
                lex[n] = " ".join(word(w) for w in r.split())
    if tour:
        root_over = json.loads((ROOT / "names" / "overrides.json").read_text(encoding="utf-8"))
        lex.update({k: v for k, v in root_over.items() if k in SHARED})
    over = base / "names" / "overrides.json"
    if over.exists():
        lex.update(json.loads(over.read_text(encoding="utf-8")))
    return lex


if __name__ == "__main__":
    tour = tour_arg()
    for part in TOURS.get(tour, [tour]):
        lex = build(part)
        ((ROOT / part) if part else ROOT).joinpath("lexicon.json").write_text(json.dumps(lex, ensure_ascii=False, indent=1), encoding="utf-8")
        if "--show" in sys.argv:
            for k, v in sorted(lex.items()):
                print(f"{k} -> {v}")
        print(f"{part or 'alhambra'}: {len(lex)} entries")
