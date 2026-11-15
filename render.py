"""Render a two-voice script to audio with Kokoro (mlx-audio).

Usage: python render.py SCRIPT.txt OUT.wav [--phonemes]

Script format: "N: text" narrator, "A: text" aside voice, "..." long pause,
"#" comment. Names in LEXICON are replaced with Kokoro's inline
pronunciation markup, [word](/phonemes/), before synthesis.
"""
import re
import sys

import numpy as np
import soundfile as sf
from mlx_audio.tts.utils import load_model

MODEL = "mlx-community/Kokoro-82M-bf16"
SR = 24000
VOICES = {"N": ("bf_emma", "b", 0.95), "A": ("bm_george", "b", 1.0)}
GAP_LINE, GAP_SPEAKER, GAP_LONG = 0.55, 0.9, 1.6

# Kokoro phoneme strings for names the English front end gets wrong.
LEXICON = {
    "Arrayanes": "ˌaɹaɪˈɑːnɛs",
    "Comares": "kɒmˈɑːɹɛs",
    "comaraxía": "kˌɒmɑːɹɑːʃˈiːə",
    "Rafael": "ɹˌafɑːˈɛl",
    "Contreras": "kɒntɹˈɛɹɑːs",
    "Leopoldo": "lˌAəpˈɒldQ",
    "Torres": "tˈɒɹɛs",
    "Balbás": "balbˈɑːs",
    "Yusuf": "jˈuːsʊf",
    "Mexuar": "mˌɛʃuːˈɑː",
    "Generalife": "hˌɛnɛɹɑːlˈiːfA",
    "Abencerrajes": "ˌabɛnsɛɹˈɑːhɛs",
    "Alcazaba": "ˌalkəsˈɑːbə",
}


def apply_lexicon(text):
    for word, ph in LEXICON.items():
        text = re.sub(rf"\b{re.escape(word)}\b", f"[{word}](/{ph}/)", text)
    return text


def main():
    script, out = sys.argv[1], sys.argv[2]
    show = "--phonemes" in sys.argv
    model = load_model(MODEL)
    parts, last = [], None
    for raw in open(script, encoding="utf-8"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line == "...":
            parts.append(np.zeros(int(SR * GAP_LONG), dtype=np.float32))
            continue
        who, text = line.split(":", 1)
        voice, lang, speed = VOICES[who]
        if last is not None:
            gap = GAP_LINE if who == last else GAP_SPEAKER
            parts.append(np.zeros(int(SR * gap), dtype=np.float32))
        last = who
        for r in model.generate(text=apply_lexicon(text.strip()), voice=voice,
                                speed=speed, lang_code=lang):
            parts.append(np.asarray(r.audio, dtype=np.float32).reshape(-1))
            if show:
                print(getattr(r, "phonemes", None) or getattr(r, "tokens", ""))
    audio = np.concatenate(parts)
    sf.write(out, audio, SR)
    print(f"{out}: {len(audio) / SR:.1f}s")


if __name__ == "__main__":
    main()
