# Spec 39 — Center the footer legal notes

The three closing lines in the footer — the copyright, the Apache
OpenServerless trademark attribution and the LaunchKit credit — are
left-aligned under a full-width block. Center them.

## Why

They are a centered-by-convention colophon, not a column of content. Ragged
left alignment across the full page width reads as an unfinished row rather
than a closing note.

## Changes

`static/css/index.css`, in the Footer section:

```css
.footer-notes {
  text-align: center;
}
```

A new class rather than an existing one: `.centered` is defined twice in this
stylesheet, but both are nested (`&.centered`) inside other rules, so neither
applies to a bare paragraph.

`templates/base.html`, the closing `<p class="paragraph s tertiary">` in the
footer: add `footer-notes` to its class list. Nothing else about the block
changes — the links, the `<br />` line breaks and the `tertiary` color stay.

## Note

`landing/css/index.css` is a byte-identical untracked copy of the served
stylesheet; `static/css/` is what zola publishes and what is in git, so only
the tracked one is edited.

## Verification

`./build.sh serve --fast`, then confirm the three footer lines are centered on
the home page and on a docs page, in both themes.
