# Spec 37 — Scene 9: make Trusty actually speak the line

`2-generation/scene9.json` renders with Trusty silent. He performs the deflated
reaction, but his mouth does not move and the narration is not spoken on camera.

## Why

`videogen.py:build_prompt` appends

```
Trusty speaks aloud, in sync with his mouth: "<speak>"
```

after the `description`, so the speech instruction is the *last* and shortest part
of the prompt. Scene 9's description works against it:

- It is the longest description in the video and is almost entirely **expression
  direction**: shoulders drop, antennae sag, "deflated and frustrated for the whole
  clip", "resigned, defeated expression".
- It then spends a sentence on **negative mouth constraints** — "No smile, no
  brightening and no relief appears at any point" — and another on holding the gaze
  steady. Held facial state reads as a held face, so H3 keeps the mouth still.
- Nothing in it says he is talking. The one speech cue is the short appended line,
  outweighed by everything above it.

Scene 9 also carries the longest `speak` line in the video (123 characters over
9 seconds), so a still mouth is especially obvious.

## Change

Rewrite `scene9.json`'s `description` only. `speak`, `start`, `end` and `duration`
are unchanged.

- **Lead with him speaking**: talking to camera for the whole clip, mouth clearly
  moving in sync with the words.
- Keep the deflated beat, but attach it to **posture, eyes and antennae** rather
  than to the mouth — sagging shoulders and a flat, tired delivery, not a held
  face.
- Restate "no smile" as being about **tone and brightening light**, not about the
  mouth being closed, so it no longer competes with lip-sync.
- Keep the diagram-to-cloud action and the final sharpening gaze.
- Keep the character-design and no-text guard sentences verbatim, as in every
  other scene.

## Note

Scenes 7 and 8 are unchanged. An earlier pass edited scene 8 on the mistaken
belief that it was the silent clip; that edit has been reverted and both files are
back to their original descriptions.

## Regenerate

```
cd video
python videogen.py --regen 9   # keeps the old clip as scene9-old<x>.mp4
```

Then re-run the post pass (spec 35) and re-concat, since scene 9's audio changes.
