# Alhambra audio guide

Turns the Alhambra walking guide (`guide/alhambra-guide.html`) into a free, offline audio tour using Kokoro, an open text-to-speech model that runs locally on Apple Silicon.

## Layout

- `guide/` snapshot of the written guide, the source for the scripts
- `scripts/` one spoken script per stop
- `render.py` renders a script to audio with two voices and a name lexicon
- `out/` rendered audio, not tracked

## Setup

    python3.12 -m venv .venv
    .venv/bin/pip install -r requirements.txt

Keep the project at a short path. The speech engine fails to find its data when the path to `.venv` is very long.

## Render

    .venv/bin/python render.py scripts/stop-03.txt out/stop-03.wav
    ffmpeg -i out/stop-03.wav -ac 1 -b:a 64k out/stop-03.mp3

## Script format

- `N: text` narrator voice
- `A: text` aside voice, for legends and thinly sourced details
- `...` on its own line is a long pause
- `#` starts a comment

Spanish and Arabic names go in `LEXICON` in `render.py` as Kokoro phoneme strings.
