# Spec 38 — Use the generated intro video on the home page

The home page hero plays `simple-intro.mp4`, hot-linked from
`https://videos.nuvolaris.download/`. Replace it with `static/intro.mp4`, the
intro video produced by specs 33–37, served from the site itself.

## Why

- The video is now ours and versioned in this repository, so there is no reason
  to depend on an external host staying up.
- Serving it from the same origin as the page removes a third-party request and
  keeps the hero working offline in a local `./build.sh serve` preview.

## Changes

`templates/landing.html`, hero `<figure class="hero-anim">`:

- `src` → `/intro.mp4` (both on the `<video>` element and in the no-video
  fallback link).
- `width`/`height` → `854` / `480`, the real dimensions of `intro.mp4`. The
  previous `1672x941` described the old clip; the attributes only set the
  intrinsic aspect ratio for layout, and a wrong one reserves the wrong box
  before the video loads.

Everything else about the block — `controls`, `playsinline`, `preload="none"`,
the `/img/splash.png` poster — stays as it is.

`static/intro.mp4` is already present; zola copies `static/` verbatim, so it is
published at `/intro.mp4` with no further wiring.

## Note

`intro.mp4` is ~14 MB and is committed to the repository, which GitHub Pages
serves directly. `preload="none"` means it is only fetched when a visitor
presses play, so it costs nothing on page load.

## Verification

`./build.sh serve --fast`, then check the hero video plays from `/intro.mp4`.
