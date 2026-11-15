# Spoken script rules

Each track is one text file in `scripts/`, rendered by text-to-speech. The listener is walking, phone in pocket, eyes on the building. Nothing visual survives: no lists, no brackets, no figures.

## File format

    # title: Stop 3. The Court of the Myrtles
    # stop: 3
    N: Narrator paragraph. Two to four sentences.
    A: Aside paragraph in the second voice.
    ...

- First line `# title:` exactly as it should show in the player. Second line `# stop:` with the stop number, or `# stop: 0` for intro tracks.
- Every spoken line starts `N: ` (narrator) or `A: ` (aside voice). One paragraph per line. Blank line between paragraphs.
- A line containing only `...` is a two-second pause. Put one after every instruction to move, turn, or look, and before and after each block of asides. Use them generously: the listener needs time to look.
- No other markup. No asterisks, no parentheses, no dashes used as punctuation, no semicolons, no quotation of URLs.

## Voice

- A calm, precise guide at the listener's shoulder. Second person, present tense. Never breathless, no "amazing" or "stunning".
- Short sentences, mostly under 20 words. One idea per sentence. Paragraphs of at most 60 words.
- Open every stop with `N: Stop three. The Court of the Myrtles.` then orientation: where the listener is standing and what is in front of them, using left, right, ahead, behind, up, down.
- Turn "Look for" lists into a guided gaze: "Look up.", "Now find the band of writing above the tiles."
- Use sound and touch where the site offers it: running water, still water, echo, cool stone.
- End every stop with one or two sentences of walking directions to the next stop, ending "That is stop four."

## Numbers and names

- Spell out every number and year as spoken: "thirteen seventy", "the middle of the thirteen hundreds", "forty-five metres", "Muhammad the Fifth", "Yusuf the First", "Charles the Fifth".
- At most two measurements per stop. Drop the rest.
- Keep Spanish and Arabic names in their normal spelling with accents (Arrayanes, Comares, Ibn Zamrak). The renderer has a pronunciation lexicon. Give the English meaning once in plain words when it helps.
- Give a foreign term at most once or twice per stop, then use the English.

## Sourcing convention, spoken

The written guide separates solid fact, "Myth check" and "Often told, thinly sourced". Keep that distinction audible:
- Solid fact: narrator, `N:`.
- Legends, myth checks, and thinly sourced details: the aside voice, `A:`, each opening with a spoken cue such as "The story goes", "You will hear that", or "Often told, though we could not confirm it". Say plainly when something is legend or disputed.
- Do not invent facts. Use only the written guide and the additions given in your brief. Keep each addition's reliability label.

## Content

- Keep the substance of each stop: the story, the architecture, the best asides. Cut dated visitor logistics, closure reports, photo links, and anything that only works on a page.
- Where the guide reports an August 2026 closure, say only that the room may be closed and to follow the signs, then describe it anyway.
- Target 450 to 750 spoken words per track. Split points are given in the brief.

See `s03-court-of-the-myrtles.txt` for a short model of the format. Real tracks should be fuller than that sample.
