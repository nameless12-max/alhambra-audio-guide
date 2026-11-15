# Alhambra audio guide

Turns the Alhambra walking guide (`guide/alhambra-guide.html`) into a free, offline audio tour using Kokoro, an open text-to-speech model that runs locally on Apple Silicon.

## Layout

- `guide/` snapshot of the written guide, the source for the scripts
- `scripts/` one spoken script per track, plus `STYLE.md`, the writing rules
- `names/` plain respellings of Spanish and Arabic names, and `overrides.json`
- `lexicon_build.py` turns the respellings into `lexicon.json`
- `render.py` renders scripts to `app/audio/*.mp3` and `app/tracks.json`
- `app/` the offline web player: synced transcript, skip, speed, download for offline
- `out/` scratch output and the audiobook file, not tracked

## Setup

    python3.12 -m venv .venv
    .venv/bin/pip install -r requirements.txt

Keep the project at a short path. The speech engine fails to find its data when the path to `.venv` is very long.

## Build

    .venv/bin/python lexicon_build.py     # after editing names/
    .venv/bin/python render.py            # renders only scripts that changed
    .venv/bin/python render.py s03        # one track
    .venv/bin/python render.py --force    # everything

Pacing (speed and pause lengths) is set at the top of `render.py`.

## Try the player

    python3 -m http.server 8765 --directory app

Open http://localhost:8765. This test server cannot seek reliably and offline install needs HTTPS, so host `app/` on any static HTTPS host to use it on a phone.
