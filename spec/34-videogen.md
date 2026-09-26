# Spec 34 — Video generation script

`video/videogen.py` renders each clip descriptor from [spec 33](33-video-clips.md)
into `video/sceneX.mp4` via the MiniMax H3 API, then concatenates them into
`video/scene.mp4`.

Source request: [video/3-videogen.md](../video/3-videogen.md).

## API

[MiniMax video generation v2](https://platform.minimax.io/docs/api-reference/video-generation-v2-create).

- **Create:** `POST https://api.minimax.io/v2/video_generation`
- **Poll:** `GET https://api.minimax.io/v2/query/video_generation/{task_id}`
- **Auth:** `Authorization: Bearer <key>`, the key taken from
  `$MINIMAX_API_KEY` or, when that is unset, from `~/.env.minimax`.
- **Model:** `MiniMax-H3-Max` — the only model offering 480P, as the request asks
  for the cheapest resolution. Its duration range is **5–15s**.
- **Result:** `task.content.url` when `task.status == "succeeded"`. The URL is
  time-limited, so download it as soon as it appears.

Request body:

```json
{
  "model": "MiniMax-H3-Max",
  "resolution": "480P",
  "duration": 6,
  "ratio": "adaptive",
  "content": [
    {"type": "text", "text": "<description + spoken line>"},
    {"type": "image_url", "role": "first_frame", "image_url": {"url": "data:image/png;base64,..."}},
    {"type": "image_url", "role": "last_frame",  "image_url": {"url": "data:image/png;base64,..."}}
  ]
}
```

## Audio

H3 generates video **with native stereo sound**, including spoken dialogue, so the
narration comes from the video model itself. The descriptor's `speak` line goes
into the prompt (`Trusty speaks aloud, in sync with his mouth: "..."`) and the
model voices it. No separate TTS pass, and no muxing.

**Reference audio is deliberately not used.** The docs are explicit: *"Image-to-video
and reference-to-video are mutually exclusive: if any `reference_image` /
`reference_video` / `reference_audio` role appears in content, then `first_frame` /
`last_frame` must not appear."* The storyboard depends on the start/end frames, so
the frames win and no `reference_audio` is sent.

### Voice consistency

Each of the 15 API calls is independent and H3 invents a voice per call. The API
exposes **no `voice_id`, no seed and no clip continuation**, so the only available
lever is the prompt. Every clip therefore carries the identical `VOICE_STYLE`
sentence describing one narrator (warm, upbeat, young adult male, medium pitch,
neutral English, cartoon quality, clean voice with no music or effects).

This steers the model but does not guarantee it: **some voice drift between clips
is expected and cannot be prevented through this API.** If the rendered result
drifts too much, the fallbacks are (a) synthesize all 16 lines with a cloned voice
via the T2A API and mux them over the clips, replacing H3's audio, or (b) switch to
reference-to-video and give up the scene images.

## Constraints discovered in the API docs

1. **480P requires `MiniMax-H3-Max`, minimum 5s.** Spec 33's duration floor was
   raised from 4s to 5s to match; `scene7`, `scene10` and `scene14` were rewritten.
2. **Frames exclude reference roles.** See Audio above.
3. **Scene 16 is built locally** and so has no dialogue; it is given a silent
   stereo track at concat time, otherwise the joined file would lose audio from
   that point on.

## Behaviour

1. Read `video/2-generation/scene*.json` in numeric order (1…16).
2. Skip any scene whose `video/sceneX.mp4` already exists — makes the script
   resumable across the long render.
3. **Static scenes** (`static: true`, i.e. scene 16): no API call. Build the clip
   locally with ffmpeg from the still image for `duration` seconds at 480p.
4. **Motion scenes:** base64-encode the `start` and `end` PNGs as data URIs, POST
   the request, then poll every 10s until `succeeded` / `failed` / `cancelled`,
   with a per-task timeout. Download `task.content.url` to `video/sceneX.mp4`.
5. Concatenate all 16 clips in order into `video/scene.mp4` with the ffmpeg concat
   demuxer, re-encoding so the API output and the locally built static clip agree
   on codec and timebase. Audio is preserved (AAC 128k stereo 44.1kHz) and the
   silent static clip is given a null stereo track so the join keeps its audio.
   Scene 16 is brought in with the 1.5s cross-fade its descriptor declares, video
   via `xfade` and audio via `acrossfade`.
6. Report per-clip status and the final duration.

## Prompt construction

The text item is the descriptor's `description`, followed by the spoken line so
the model lip-syncs it, followed by a no-text guard:

```
<description>

Trusty speaks these words during the clip: "<speak>"

Do not render any subtitles, captions, speech bubbles or written text.
```

Capped at the API's 7000-character limit.

## Script form

- Run with `uv run video/videogen.py`, deps embedded in PEP 723 inline metadata
  (`httpx`). No virtualenv setup.
- API key from `$MINIMAX_API_KEY`, falling back to `~/.env.minimax`
  (`MINIMAX_API_KEY=...`); exit with a clear message if neither has it. The key
  is never logged, and the file stays outside the repo.
- Flags: `--dry-run` (build and print requests without calling the API),
  `--limit N` (generate at most the first N clips in scene order, default all —
  for cheap test runs), `--only N` (single scene), `--force` (re-render even if
  the mp4 exists), `--no-concat` (skip the final join).
- `scene.mp4` is only built from a complete set of 16 clips, so a `--limit` or
  `--only` run never leaves a truncated file looking like the finished video.
- Failures are per-scene: report and continue, so one bad scene does not lose the
  rest. Exit non-zero if any scene failed.

## Plan

1. Write `video/videogen.py` per the above.
2. Verify with `--dry-run` that all 16 requests build, frames resolve, durations
   are in the 5–15s range and prompts are under the character cap.
3. Leave the real render to the user — it costs API credits.

## Notes

- Cost scales with total seconds: 111s across 16 clips, 101s of it billable API
  render (scene 16 is built locally).
- `scene.mp4` carries H3's generated narration; see **Audio**.
- `0-reference/trusty-ant.mp3` is unused by this script — it is the reference kept
  for the voice work described in [spec 35](35-fixvoice.md).
