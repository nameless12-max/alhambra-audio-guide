"""Compile a tour's scripts into one readable Markdown file for review.

Usage: python compile_text.py prado
"""
import re, sys
from pathlib import Path
tour = sys.argv[1]
root = Path(__file__).parent / tour
out, total = [f"# {tour.title()} tour: full text\n"], 0
for p in [q for q in sorted((root / "scripts").glob("*.txt")) if not q.name.startswith("_")]:
    words = 0
    body = []
    title = p.stem
    room = ""
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        m = re.match(r"#\s*title:\s*(.+)", s)
        if m:
            title = m.group(1); continue
        m = re.match(r"#\s*room:\s*(.+)", s)
        if m:
            room = m.group(1); continue
        if s.startswith("# "):
            continue
        if s.startswith("##"):
            body.append(f"\n### {s.lstrip('#').strip()}\n"); continue
        if set(s) <= set(". …"):
            continue
        m = re.match(r"([NA]):\s*(.+)", s)
        if not m:
            body.append(f"**BAD LINE:** {s}"); continue
        words += len(m.group(2).split())
        body.append((f"> *Legend voice:* {m.group(2)}" if m.group(1) == "A" else m.group(2)) + "\n")
    total += words
    out.append(f"\n## {title}{' · Room ' + room if room else ''}\n\n*{words} words, about {words/140:.1f} min*\n")
    out += body
out.insert(1, f"\n{total} words, about {total/140*1.15:.0f} minutes with pauses.\n")
(root / f"{tour}-tour.md").write_text("\n".join(out), encoding="utf-8")
print(tour, total, "words")
