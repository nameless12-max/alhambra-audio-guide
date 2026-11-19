"""Render the spoken scripts to audio with Kokoro (mlx-audio).

Usage:
    python render.py              render every script that changed
    python render.py s03 s05a     render only tracks whose id starts with these
    python render.py --force      re-render everything
    python render.py --tour prado render another tour (prado/scripts,
                                  prado/lexicon.json -> app/prado/)
    python render.py --tour madrid  render a combined tour: scripts from every
                                  part in TOURS (prado/, reina/) -> app/madrid/

Reads scripts/*.txt and lexicon.json. Writes app/audio/<id>.mp3 and
app/tracks.json, which holds sections and per-sentence timings for the player.

Script format: see scripts/STYLE.md.
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).parent
TOUR = sys.argv[sys.argv.index("--tour") + 1] if "--tour" in sys.argv else None
# A combined tour reads several parts; each part's tracks are tagged with its group.
TOURS = {"madrid": ["prado", "reina"], "toledo": ["toledo_sights", "toledo_cathedral", "toledo_legends", "toledo_dark"]}
GROUPS = {"prado": "Prado", "reina": "Reina Sofía", "toledo_legends": "Legends", "toledo_sights": "Sights", "toledo_cathedral": "Cathedral", "toledo_dark": "Inquisition"}
if TOUR:
    PARTS = TOURS.get(TOUR, [TOUR])
    SCRIPT_DIRS = [ROOT / p / "scripts" for p in PARTS]
    LEXICON_FILES = [ROOT / p / "lexicon.json" for p in PARTS]
    AUDIO = ROOT / "app" / TOUR / "audio"
    CACHE = ROOT / "out" / TOUR / "timings"
    TRACKS = ROOT / "app" / TOUR / "tracks.json"
else:
    PARTS = []
    SCRIPT_DIRS = [ROOT / "scripts"]
    LEXICON_FILES = [ROOT / "lexicon.json"]
    AUDIO = ROOT / "app" / "audio"
    CACHE = ROOT / "out" / "timings"
    TRACKS = ROOT / "app" / "tracks.json"
# Group label per script folder, only for combined tours.
GROUP_OF = {ROOT / p / "scripts": GROUPS.get(p, p) for p in PARTS} if TOUR in TOURS else {}

MODEL = "mlx-community/Kokoro-82M-bf16"
SR = 24000
# voice, language code, speed. Each paragraph is spoken in one pass so the
# voice keeps its natural melody across sentences.
BEAT_QUESTION, BEAT_SHORT = 0.6, 0.4
VOICES = {"N": ("af_bella", "b", 0.94), "A": ("bm_george", "b", 0.95)}
# Seconds of silence. Pacing lives here.
GAP_PARAGRAPH = 1.2
GAP_SPEAKER = 1.5
GAP_LONG = 2.4
LEAD_IN, LEAD_OUT = 0.4, 1.0


def load_lexicon():
    lex = {}
    for f in LEXICON_FILES:
        if f.exists():
            lex.update(json.loads(f.read_text(encoding="utf-8")))
    return sorted(lex.items(), key=lambda kv: -len(kv[0]))


def apply_lexicon(text, lexicon):
    for word, ph in lexicon:
        text = re.sub(rf"(?<![\w\[]){re.escape(word)}(?![\w\]])", f"[{word}](/{ph}/)", text)
    return text


def parse(path):
    """Return (title, stop, room, items).

    Items are ("pause",), ("section", heading) or (who, text).
    """
    title, stop, room, items = path.stem, 0, "", []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("##"):
            items.append(("section", line.lstrip("#").strip()))
            continue
        if line.startswith("#"):
            m = re.match(r"#\s*(title|stop|room):\s*(.+)", line)
            if m and m.group(1) == "title":
                title = m.group(2).strip()
            elif m and m.group(1) == "room":
                room = m.group(2).strip()
            elif m:
                stop = int(m.group(2))
            continue
        if set(line) <= set(". …"):
            items.append(("pause",))
            continue
        m = re.match(r"([NA]):\s*(.+)", line)
        if not m:
            raise ValueError(f"{path.name}: bad line: {line[:60]}")
        items.append((m.group(1), m.group(2)))
    return title, stop, room, items


def sentences(text):
    return [s for s in re.split(r"(?<=[.!?])[\"”’']?\s+", text) if s.strip()]


def beat_groups(sents):
    """Split a paragraph into groups spoken in one breath, with the pause after each."""
    groups, cur = [], []
    for i, s in enumerate(sents):
        cur.append(s)
        if i == len(sents) - 1:
            groups.append((cur, 0.0))
            break
        short = len(s.split()) <= 3 or len(sents[i + 1].split()) <= 3
        if s.rstrip("\"”’'").endswith(("?", "!")):
            groups.append((cur, BEAT_QUESTION)); cur = []
        elif short:
            groups.append((cur, BEAT_SHORT)); cur = []
    return groups


def silence(seconds):
    return np.zeros(int(SR * seconds), dtype=np.float32)


def sentence_bounds(audio, sents):
    """Estimate where each sentence starts inside one paragraph of audio.

    Guess each boundary from text length, then snap it to the quietest
    moment nearby, which is the pause between sentences.
    """
    n = len(audio)
    if len(sents) < 2:
        return [0.0, n / SR]
    hop = int(SR * 0.02)
    env = np.abs(audio[: n - n % hop]).reshape(-1, hop).mean(axis=1)
    env = np.convolve(env, np.ones(5) / 5, mode="same")
    weights = np.array([len(s) + 8 for s in sents], dtype=float)
    cuts = np.cumsum(weights)[:-1] / weights.sum() * len(env)
    # No sentence can be shorter than its text allows, in 20 ms hops.
    least = [max(25, int(len(s) * 2.2)) for s in sents]
    loud = np.nonzero(env > env.max() * 0.05)[0]
    speech_start = int(loud[0]) if len(loud) else 0
    bounds, prev = [0], speech_start
    for i, c in enumerate(cuts):
        lo = max(prev + least[i], int(c) - 40)
        hi = min(len(env) - sum(least[i + 1:]), int(c) + 40)
        k = lo + int(np.argmin(env[lo:hi])) if hi > lo else min(lo, len(env) - 1)
        bounds.append(k)
        prev = k
    return [b * hop / SR for b in bounds] + [n / SR]


def render(path, model, lexicon):
    title, stop, room, items = parse(path)
    parts, segments, sections, t = [silence(LEAD_IN)], [], [], LEAD_IN
    last_who, pending, para, new_section = None, 0.0, -1, None
    for item in items:
        if item[0] == "pause":
            pending = max(pending, GAP_LONG)
            continue
        if item[0] == "section":
            new_section = item[1]
            continue
        who, text = item
        para += 1
        voice, lang, speed = VOICES[who]
        if last_who is not None:
            gap = max(pending, GAP_PARAGRAPH if who == last_who else GAP_SPEAKER)
            parts.append(silence(gap))
            t += gap
        pending, last_who = 0.0, who
        if new_section is not None or not sections:
            sections.append({"title": new_section or "Start", "start": round(max(0.0, t - 0.3), 2)})
            new_section = None
        # Speak the paragraph in beats: a breath after a question and around a
        # short punchy sentence, so dramatic lines are not rushed.
        sents = sentences(text)
        pieces, bounds, off = [], [], 0.0
        for group, gap in beat_groups(sents):
            chunks = [np.asarray(r.audio, dtype=np.float32).reshape(-1)
                      for r in model.generate(text=apply_lexicon(" ".join(group), lexicon),
                                              voice=voice, speed=speed, lang_code=lang)]
            a = np.concatenate(chunks)
            bounds += [off + b for b in sentence_bounds(a, group)[:-1]]
            pieces.append(a)
            off += len(a) / SR
            if gap:
                pieces.append(silence(gap))
                off += gap
        bounds.append(off)
        audio = np.concatenate(pieces)
        parts.append(audio)
        for i, sent in enumerate(sents):
            segments.append({"p": para, "s": len(sections) - 1, "who": who, "text": sent,
                             "start": round(t + bounds[i], 2), "end": round(t + bounds[i + 1], 2)})
        t += len(audio) / SR
    parts.append(silence(LEAD_OUT))
    audio = np.concatenate(parts)
    AUDIO.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    wav = CACHE / f"{path.stem}.wav"
    sf.write(wav, audio, SR)
    mp3 = AUDIO / f"{path.stem}.mp3"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(wav),
                    "-ac", "1", "-b:a", "48k", str(mp3)], check=True)
    wav.unlink()
    # The version tag makes phones fetch a re-rendered file instead of a saved old one.
    version = hashlib.sha1(mp3.read_bytes()).hexdigest()[:8]
    meta = {"id": path.stem, "title": title, "stop": stop,
            "file": f"audio/{path.stem}.mp3?v={version}",
            "duration": round(len(audio) / SR, 2), "bytes": mp3.stat().st_size,
            "sections": sections, "segments": segments}
    if path.parent in GROUP_OF:
        meta["group"], meta["room"] = GROUP_OF[path.parent], room
    (CACHE / f"{path.stem}.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return meta


def main():
    argv = sys.argv[1:]
    if "--tour" in argv:
        i = argv.index("--tour")
        argv = argv[:i] + argv[i + 2:]
    args = [a for a in argv if not a.startswith("--")]
    force = "--force" in sys.argv
    lexicon = load_lexicon()
    lex_mtime = max([f.stat().st_mtime for f in LEXICON_FILES if f.exists()], default=0)
    model, tracks = None, []
    for path in [p for d in SCRIPT_DIRS for p in sorted(d.glob("*.txt")) if not p.name.startswith("_")]:
        cached = CACHE / f"{path.stem}.json"
        mp3 = AUDIO / f"{path.stem}.mp3"
        wanted = not args or any(path.stem.startswith(a) for a in args)
        fresh = (cached.exists() and mp3.exists()
                 and cached.stat().st_mtime > max(path.stat().st_mtime, lex_mtime))
        if wanted and (force or args or not fresh):
            if model is None:
                from mlx_audio.tts.utils import load_model
                model = load_model(MODEL)
            meta = render(path, model, lexicon)
            print(f"{path.stem}: {meta['duration'] / 60:.1f} min, {len(meta['sections'])} sections", flush=True)
        elif cached.exists() and mp3.exists():
            meta = json.loads(cached.read_text(encoding="utf-8"))
        else:
            continue
        tracks.append(meta)
    TRACKS.parent.mkdir(parents=True, exist_ok=True)
    TRACKS.write_text(json.dumps({"tracks": tracks}, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(t["duration"] for t in tracks)
    size = sum(t["bytes"] for t in tracks)
    print(f"{len(tracks)} tracks, {total / 60:.0f} min, {size / 1e6:.0f} MB")


if __name__ == "__main__":
    main()
