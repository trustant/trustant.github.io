# Spec 32 — Move the canonical domain to trustant.ai

## Problem

The site is served from `trustant.ai` (spec 31), but `base_url` in
`config.toml` was still `https://trustable.it`. Zola builds every internal
permalink from `base_url`, so the published pages linked back to the old
domain: the Documentation item in the nav pointed at
`https://trustable.it/documentation`, and the sitemap, canonical URLs and the
published catalog all named the old host.

## Plan

1. `config.toml`: `base_url = "https://trustant.ai"`.
2. `static/CNAME`: `trustant.ai`, so the domain is stated once in the source
   the build copies from.
3. `build.sh`: drop the `docs/CNAME` override added in spec 31. It existed only
   because `static/CNAME` disagreed with the domain being served; with the
   source corrected the override is redundant, and two places writing the same
   file is what lets them drift.
4. `generator.py`: derive `SITE` from `base_url` instead of repeating the
   domain as a second hardcoded constant.

## The generator held a second copy of the domain

`generator.py` had its own `SITE = "https://trustable.it"`, with a comment
saying it must match `base_url`. Nothing enforced that, and this change is
exactly the case the comment warned about — updating `config.toml` alone would
have left the published catalog handing out icon URLs on the old host. `SITE`
is now read from `config.toml` with `tomllib`, so the domain is stated once.

## Icon reuse has to survive a domain change

Changing `SITE` exposed a latent bug in how a catalog is read back.

On `--offline`/`--fast` the generator re-reads `static/index.json` and
recognises its own icons so it can keep them, by testing
`icon.startswith(SITE + "/images/")`. That test asks whether the icon sits on
*today's* domain. After the move, every icon written by a previous run named
the old one, failed the test, was taken for a foreign URL, and had the new
origin pasted in front of the old:

    https://trustant.aihttps://trustable.it/images/<file>.png

It compounded on each offline rebuild. Worse, an unrecognised icon is never
marked as used, so `clean_images()` deleted the very file it named — one
screenshot was lost this way and had to be re-fetched by a full build.

An icon is now recognised by its generator-owned `/images/<file>` tail
whatever origin precedes it, **and** by the file actually being present in
`static/images/`. The path alone is not proof, since a README hotlinking
someone else's screenshot can end in `/images/<file>` too; holding the file is
what distinguishes our own catalog read back. Matching the tail rather than one
leading origin also repairs a catalog already left with stacked origins.

## Out of scope

The ~25 content files under `content/` still say "Trustable" in body prose, as
they did before; that remains an editorial pass.

## Verification

- No `trustable.it` anywhere under `docs/`.
- The reported link is now `https://trustant.ai/documentation/`; `sitemap.xml`
  and the canonical URLs name `trustant.ai`; `docs/CNAME` reads `trustant.ai`,
  written from `static/CNAME` with no override in `build.sh`.
- All 13 catalog icons are `https://trustant.ai/images/<file>`, with no stacked
  origins, and all 13 images are present in `static/images/`.
- Two further offline rebuilds leave both the icons and the image count
  unchanged, so the read-back path is idempotent across a domain change.
