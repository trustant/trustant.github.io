# Spec 41 — Drop the LaunchKit credit; open source box after the prices

## Why

The MIT license of LaunchKit only requires the copyright and permission notice
to travel with the code, not a visible credit on the page. The repository keeps
`landing/LICENSE`; the published `css/index.css` (the LaunchKit base) gets the
notice as a header comment so it ships with the site too. The open source statement is a selling point and
belongs right after the prices, styled like them.

## Plan

`templates/base.html`, footer brand column:

- Remove the "Page built with LaunchKit by Evil Martians." line (and the `<br />`
  before it). Copyright and the OpenServerless trademark notes stay.

`static/css/index.css`:

- Prepend a comment with the LaunchKit MIT copyright and permission notice.

`templates/landing.html`:

- Move `<section id="credits">` from after the FAQ to directly after
  `<section id="pricing">`; renumber the section comments.
- Give its `.tech-foundation` box the `feature-card` class so it gets the same
  surface background, rounded corners and padding as the price cards.

`static/css/trustant.css`:

- `#credits .tech-foundation`: no top margin, centered content (overriding
  `feature-card`'s `flex-start`).
- `#credits`: tight top/bottom padding, joining the pricing run like `#pricing`.

## Hero title accent

`templates/landing.html`: in the hero `<h1>` "A Trustable Code Assistant for
Private AI", wrap "Trustable" and "Private AI" in `<span class="accent-text">`.

`static/css/trustant.css`: `.accent-text { color: var(--color-accent); }` (the
burnt orange `#e2703a`, already AA on the dark ground). The page `<title>` stays
plain text.

## Verification

`./build.sh serve --fast`: the footer has no LaunchKit line; on the home page
the open source box sits under the three price cards, rounded and tinted like
them, in both themes and at mobile width; the nav "OpenSource" link still
scrolls to it; in the hero title "Trustable" and "Private AI" are orange.
