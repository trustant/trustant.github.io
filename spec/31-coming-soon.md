# Spec 31 — Publish behind a "Coming soon" placeholder, on trustant.ai

## Goal

The generated site is complete but not yet announced. Publish it so that the
real home page is reachable at its own URL while visitors to the root still see
a holding page, and serve the result from the new domain.

## Plan

Two steps added to `build.sh`, after zola has written `docs/` and before the
build's commit. They run for `build` and `push` alike — `serve` has already
exec'd away by that point, so a local preview is unaffected and still shows the
real home page at `/`.

### 1. Swap the home page

- `docs/index.html` (generated from `templates/landing.html`) is renamed to
  `docs/index1.html`.
- The repo-root `index.html` — the "Coming soon" placeholder — is copied over
  `docs/index.html`.

So `/` is the placeholder and `/index1.html` is the real page. This mirrors the
`landing` repo, which arranges its own two pages the same way.

The swap is reapplied on every build rather than kept in `docs/` by hand,
because zola wipes and rewrites its output directory each run. The build fails
with a clear message if the placeholder is missing, rather than publishing a
site whose front page is the one it was meant to hide.

### 2. Write the domain

`docs/CNAME` is written as `trustant.ai`.

It is written by the script rather than changed in `static/CNAME`, which zola
copies into `docs/` verbatim on every build: that file still carries
`trustable.it` for the existing site, and the two are deliberately kept apart.

## Placeholder asset paths

The root `index.html` came from the `landing` repo and referenced its assets
relatively — `images/logo-trustant.png`, `images/trusty-ant.png`,
`images/favicon/*` and `fonts/InterVariable.woff2`. This site publishes those
under `/img/` and `/favicon/` instead, so every one of them would have 404'd:
the placeholder would have rendered as unstyled text with no logo and no
mascot. The paths are rewritten to the site-absolute ones.

## Out of scope

`config.toml`'s `base_url` is still `https://trustable.it`, so the canonical
URLs, sitemap and feed in the built output name the old domain even though the
site is now served from `trustant.ai`. Changing it is a separate step.

## Verification

`./build.sh build` reports both steps. In the built output, `/` carries the
title "Trustant — Coming Soon" and `/index1.html` carries "Trustant — A
Trustable Code Assistant for Private AI"; `docs/CNAME` reads `trustant.ai`
while `static/CNAME` is untouched. Served locally, both pages and all of the
placeholder's assets return 200, and the placeholder renders with its logo,
mascot and web font.
