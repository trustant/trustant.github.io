# Spec 35 — Fix the narrator voice in post

`video/fixvoice.py` replaces the inconsistent narration in `2-generation/scene.mp4`
with a single uniform voice, using ElevenLabs Voice Changer on fal.ai.

Source request: [video/3-fixvoice.md](../video/3-fixvoice.md).

## Why

H3 generated each clip in a separate call, and the API exposes no voice id, seed
or continuation (see [spec 34](34-videogen.md)). The rendered clips drifted badly.
Measured median pitch per clip:

| | |
| --- | --- |
| Range | 139.7 Hz (scene 5) → 225.4 Hz (scene 6) |
| Spread | **85.6 Hz** |
| Overall median | 169.3 Hz |

Six clips sit more than 15 Hz off the median (scene 6 at +56 Hz, scene 5 at
−30 Hz). That is audibly several different speakers, so the narration has to be
unified in post.

Voice Changer is speech-to-speech: it re-voices the existing audio and keeps its
timing, so **H3's lip-sync survives**. Re-synthesising from text (TTS) would not.

## Pipeline

1. **Extract** — `2-generation/scene.mp4` → `3-postprod/scene.mp3`, skipped if the
   file is already there.
2. **Convert** — one `fal-ai/elevenlabs/voice-changer` call over the whole track,
   target voice **`Will`** → `3-postprod/scene-will.mp3`. A single pass guarantees
   one uniform voice. The output is named after the voice, so trying another
   preset with `--voice` yields `scene-<name>.mp3` beside it rather than
   overwriting.
3. **Mux** — the converted audio back onto the original video →
   `3-postprod/scene-will.mp4`, video stream copied, audio re-encoded to AAC.

Each step is skipped when its output exists, so a re-run is cheap. `--force`
redoes everything.

## API

[fal-ai/elevenlabs/voice-changer](https://fal.ai/models/fal-ai/elevenlabs/voice-changer/api).

- **Submit:** `POST https://queue.fal.run/fal-ai/elevenlabs/voice-changer`
- **Poll / result:** the `status_url` and `response_url` the submit returns
- **Auth:** `Authorization: Key <FALAI_API_KEY>`
- **Input:** `audio_url` (a data URI is accepted), `voice`, `remove_background_noise`,
  optional `seed`, `output_format`
- **Output:** the converted audio URL in `audio.url`

## Constraint found in the API docs

**`voice` takes a preset ElevenLabs voice name or id, not reference audio.** The
default is `"Rachel"`. There is no parameter that accepts a sample to imitate, so
**`0-reference/trusty-ant.mp3` cannot be used as the target voice** as the original
request assumed.

The script therefore uses a preset. The chosen target is **`Will`** (a young,
upbeat male voice), overridable with `--voice`. The result is perfectly consistent
but will not sound like `trusty-ant.mp3`. Matching that reference would mean
cloning it at ElevenLabs directly for a custom `voice_id`, which needs an
`ELEVENLABS_API_KEY` that `~/.env.minimax` does not hold.

The accepted preset names, from fal.ai's own endpoint schema: Aria, Roger, Sarah,
Laura, Charlie, George, Callum, River, Liam, Charlotte, Alice, Matilda, Will,
Jessica, Eric, Chris, Brian, Daniel, Lily, Bill. The API default is `Rachel`.

The request also names `0-reference/trusty-ant.mp4`; only `trusty-ant.mp3` exists.
It is unused either way, per the constraint above.

## Script form

- `uv run video/fixvoice.py`, PEP 723 inline deps (`httpx`).
- Keys from `~/.env.minimax` (`FALAI_API_KEY`; `MINIMAX_API_KEY` is also there but
  unused here), environment overriding the file.
- Flags: `--voice NAME` (default `Will`), `--force`, `--keep-noise` (skip
  background-noise removal), `--seed N`, `--sample N` (convert only the first N
  seconds, to audition a voice cheaply before committing to the full 115s).
- Reports the measured pitch spread before and after, so the fix is verifiable
  rather than assumed.

## Plan

1. Write `video/fixvoice.py` per the above.
2. Extract the audio locally and confirm the pitch measurement reproduces.
3. Leave the fal.ai call to the user — it costs credits.

## Notes

- Only the audio changes; the video stream is copied, so no re-render.
- `3-postprod/scene-will.mp4` is the deliverable.
