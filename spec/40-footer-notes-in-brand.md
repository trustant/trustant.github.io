# Spec 40 — Move the legal notes into the brand column, left-aligned

Spec 39 centered the closing legal notes in their own full-width row under the
footer menu. Move them instead into the first footer column, directly below the
"A coding assistant for Private AI" tagline, left-aligned.

## Why

The notes belong with the brand they are about — the copyright, the trademark
attribution and the build credit all describe who made the page, which is what
the first column already says. As a separate full-width row they read as a
detached band; in the brand column they close the column that introduces the
site, and the footer becomes three columns rather than three columns plus a
stripe.

This supersedes spec 39: the centering added there is removed.

## Changes

`templates/base.html`, footer:

- Move the closing `<p>` out of its own `<div>` (after `.footer-menu`) and into
  `div.footer-brand`, after the tagline paragraph. Delete the now-empty wrapper
  `<div>`.
- Drop the `footer-notes` class from the paragraph; it keeps
  `paragraph s tertiary`. Left alignment is then simply the inherited default,
  so no class is needed to express it.

`static/css/index.css`:

- Remove the `.footer-notes` rule added by spec 39. Nothing else references it.

## Layout

The brand column is the `2fr` track of the footer's `2fr 1fr 1fr` grid, so the
notes wrap within roughly half the page width instead of running its full
width. On mobile `.footer-menu` collapses to a single column, where the notes
follow the tagline in document order — the same reading order as the desktop
column.

## Verification

`./build.sh serve --fast`, then confirm on the home page and a docs page:
the three lines sit under the tagline, left-aligned, in both themes, and at
mobile width they still follow the tagline.
