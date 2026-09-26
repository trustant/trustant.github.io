# Spec 33 — Video clip descriptors

Generate one JSON descriptor per video clip, so an image-to-video model can render
the Trustant intro video from the existing storyboard images.

## Sources

| Source | Role |
| --- | --- |
| [video/1-subject.md](../video/1-subject.md) | Story, 16 storyboard beats, narration, captions |
| [video/2-script.md](../video/2-script.md) | Requested output format |
| `video/1-guide/scene*.txt` | Per-scene visual specification and spoken dialogue |
| `video/1-guide/scene*.png` | First-pass scene renders (reference only) |
| `video/2-generation/scene*.png` | Final scene images — the frames the clips interpolate |
| `video/0-reference/trusty-ant.mp3` | Isolated voice reference for narration timing/tone |

## Decisions

- **Clip mapping: consecutive pairs.** Clip *N* runs from `2-generation/sceneN.png` to
  `2-generation/sceneN+1.png`, giving **15 clips** from the 16 images. Each clip is a
  transition between two storyboard beats rather than motion inside one frame.
- **Narration:** clip *N* carries scene *N*'s spoken dialogue, verbatim from
  `1-guide/sceneN.txt`. Clips 1–15 therefore cover scenes 1–15.
- **Scene 16 is not an interpolated clip.** The motion ends at clip 15, whose
  `end` frame is `2-generation/scene16.png`. Scene 16 is then held as a static closing
  card, reached by a cross-fade out of scene 15. Its closing narration plays over
  that hold. The fade and hold are an editing-stage operation, not something the
  image-to-video model renders, so scene 16 gets a descriptor of its own
  (`scene16.json`) marked as a static ending rather than a start/end pair.
- **Duration:** derived from the narration at ~150 wpm (2.5 words/second), plus
  ~1.2s of breathing room, rounded up to whole seconds, with a **5s floor** — both
  so short lines still read as a shot and because `MiniMax-H3-Max`, the model that
  offers 480p, will not accept a clip shorter than 5s (see
  [spec 34](34-videogen.md)).

## Output

`video/2-generation/sceneX.json` — one file per clip, `scene1.json` … `scene16.json`.

**Clips 1–15 — interpolated motion:**

```json
{
  "start": "2-generation/scene1.png",
  "end": "2-generation/scene2.png",
  "speak": "Hi! I'm Trusty. I have an idea for a new application.",
  "description": "<camera and subject motion carrying start frame to end frame>",
  "duration": 5
}
```

- `start` / `end` — repo-relative paths under `video/`.
- `speak` — narration, verbatim from the guide. It sets the clip's duration, and
  is embedded in the prompt sent to the video model so Trusty is animated speaking
  those words; the API has no separate spoken-text input (see
  [spec 34](34-videogen.md)).
- `description` — the motion between the two frames: what the camera does, how
  Trusty moves and reacts, what appears or dissolves. Written for an
  image-to-video model, keeping the 3D-cartoon style and scene continuity from
  the guide files. No captions or on-screen text, matching the guide directive.
- `duration` — whole seconds, per the rule above.

**Scene 16 — static ending.** Same keys, so a single loader reads every file, but
`start` and `end` are both `2-generation/scene16.png` and the extra `static` and
`transition` keys tell the pipeline to hold the frame instead of calling the
video model:

```json
{
  "start": "2-generation/scene16.png",
  "end": "2-generation/scene16.png",
  "static": true,
  "transition": "crossfade from 2-generation/scene15.png, 1.5s",
  "speak": "Private AI was only the beginning. ...",
  "description": "<the held closing card>",
  "duration": 11
}
```

## Plan

1. Extract the 16 narration lines from `video/1-guide/scene*.txt`.
2. Compute each clip's duration from its narration word count.
3. For each of the 15 clips, write the motion `description` from the two scenes'
   guide text — what changes between the frames.
4. Write the scene 16 static ending descriptor, with its cross-fade in from
   scene 15 and its closing narration.
5. Write `video/2-generation/scene1.json` … `scene16.json`.
6. Report the per-clip and total duration.

## Notes

- The guide files forbid on-screen text; `description` must not reintroduce it.
- Captions from `1-subject.md` stay out of the JSON — they are an editing-stage
  overlay, not part of the clip render.
