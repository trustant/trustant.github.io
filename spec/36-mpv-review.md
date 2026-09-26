# Spec 36 — mpv review tooling

A local mpv setup for watching the generated video with sound and marking the
frame ranges that need fixing.

## Why

Reviewing `2-generation/scene.mp4` means hearing the narration and noting exactly
where a clip goes wrong. Marking the start and end frame of each problem range
gives the next fix pass precise boundaries instead of prose timestamps.

## Files

| File | Role |
| --- | --- |
| `video/mpv.sh` | Launcher — points mpv at the config and loads the script |
| `video/mpv/mpv.conf` | Playback and screenshot settings |
| `video/mpv/input.conf` | Transport keybindings |
| `video/mpv/scripts/fixmark.lua` | The `s` / `S` mark bindings |

## Behaviour

```
cd video
./mpv.sh 2-generation/scene.mp4
./mpv.sh 3-postprod/scene-will.mp4 --start=30
```

Marking:

| Key | Writes |
| --- | --- |
| `s` | `3-postprod/fix-<frame>-start.png` |
| `S` | `3-postprod/fix-<frame>-stop.png` |

Transport:

| Key | Action |
| --- | --- |
| `SPACE` | play / pause |
| `UP` / `DOWN` | ±5 seconds |
| `RIGHT` / `LEFT` | ±1 second |
| `Shift+RIGHT` / `Shift+LEFT` | ±1 frame |

All seeks are `exact`, not keyframe-snapped, so the frame marked by `s` / `S` is
the frame that was on screen. Default mpv seeking would snap to the nearest
keyframe and the mark could land up to a second away.

`<frame>` is mpv's `estimated-frame-number` at the moment the key is pressed,
falling back to `playback-time × container-fps` before the first frame decodes.
There is no run id or slot number — the frame number alone names the file, so
re-marking the same frame overwrites rather than accumulating duplicates.

Screenshots are full-resolution PNG taken in mpv's `video` mode, so the OSD
feedback and any subtitles are not burned in. Verified at 854×480, matching the
source.

Extra arguments after the filename pass through to mpv.

## Config

- **Audio enabled explicitly** (`audio=auto`, `mute=no`, `volume=100`) — the point
  of the review is hearing the generated narration.
- **`screenshot-format=png`**, high bit depth, no scaling — full-resolution stills.
- **`hr-seek=yes`** and no frame dropping, so stepping lands on the intended frame.
- **`keep-open=yes`** — playback stops on the last frame instead of quitting, so
  the final frame can still be marked.
- `autofit-larger=90%x90%` keeps the window sane without upscaling the 854×480
  clips.

The output directory reaches the Lua script through `FIXMARK_OUTDIR`, which
`mpv.sh` exports; it falls back to `./3-postprod`.

## Note

mpv 0.41 does **not** auto-load `scripts/` from a `--config-dir` given on the
command line — the script silently never runs. `mpv.sh` therefore passes
`--script=` explicitly. This was found in testing, not assumed. `input.conf` and
`mpv.conf` *are* picked up from the config dir normally.

`s` and `S` are mpv's own screenshot bindings by default; both are rebound here.

## Verification

Driven through mpv's IPC socket rather than by eye:

| Action | Result |
| --- | --- |
| `s` at 10s | `fix-250-start.png` (24.97 fps → frame 250) |
| `S` at 30s | `fix-749-stop.png` |
| Resolution | 854×480 PNG, identical to source |
| `SPACE` | `pause` toggled True → False |
| `UP` / `DOWN` | 20.000 → 25.000 → 20.000 s |
| `RIGHT` / `LEFT` | 20.000 → 21.000 → 20.000 s |
| `Shift+RIGHT` / `Shift+LEFT` | 20.000 → 20.040 → 20.000 s (one frame) |
