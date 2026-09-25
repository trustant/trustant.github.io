# Spec 30 — Rebrand to Trustant, new homepage from `landing/`

## Goal

Replace the Trustable-branded homepage and site chrome with the Trustant
landing page that lives in the `landing/` submodule, converted to the site's
Zola templating, and rebrand the shared chrome (logo, favicon, style, nav,
social links) across the whole site.

## Source material

`landing/` is the `trustant/website` submodule (LaunchKit template, Evil
Martians). Two HTML files are there:

- `landing/index.html` — a placeholder "Coming soon" page. **Not the source.**
- `landing/index1.html` — the real landing page, 9 sections. **This is the
  source** for the new homepage.

Assets to bring across from `landing/`:

| From | To (`static/`) |
| --- | --- |
| `css/index.css`, `pricing.css`, `tablet.css`, `mobile.css`, `trustant.css` | `static/css/` |
| `js/main.js` | `static/js/main.js` |
| `fonts/InterVariable.woff2`, `JetBrainsMono-VariableFont_wght.ttf` | `static/fonts/` |
| `vendor/font-awesome-6.7.2/` | `static/vendor/font-awesome-6.7.2/` |
| `images/favicon/*` | `static/favicon/` |
| `images/logo-trustant.png`, `logo-nuvolaris.svg`, `trusty-ant.png`, and the section images (`mac+spark.png`, `local-ai.png`, `private-ai.png`, `sovereign-ai.png`, `nuvolaris-stack.png`, `apache-openserverless.png`, `opensource.png`, `splash.png`) | `static/img/` |
| `images/templates/*.png` | not copied — the gallery already generates its own icons into `static/images/` via `generator.py` |

**`static/img/`, not `static/images/`.** `generator.py` owns `static/images/`
outright: its `clean_images()` deletes every file there it did not just
download, so brand artwork placed in it is removed on the next build ("no
hand-written file belongs in it", generator.py:53). The site's own artwork
therefore lives in `static/img/` and the two directories never collide.

Font Awesome ships with web fonts under `vendor/font-awesome-6.7.2/`; copy the
whole directory so `all.min.css` resolves its `../webfonts/` references.

## Plan

### 1. Assets

Copy the table above into `static/`. Keep the directory names so the paths in
the copied CSS keep resolving. Do not commit `landing/` itself into the build —
it stays a submodule and is only the source.

### 2. `templates/landing.html` — the new homepage

Rewrite it as a Zola template extending `base.html`, carrying the nine sections
of `index1.html` verbatim in structure:

1. Hero — logo, `<h1>`, typewriter motto list, intro video
2. Pricing — three plans (Personal / Developer / Enterprise)
3. How it works — three numbered steps + the publish-destination flow diagram
4. Powered by Nuvolaris — stack description and diagram
5. Templates — **replaced**: instead of the hardcoded `template-rail`, render
   the existing `starter-cards.html` gallery so the catalogue stays generated
   from `static/index.json` rather than frozen into the page
6. Platform — the four-layer stack diagram and three feature cards
7. FAQ — the `<details>` accordion
8. Credits — Apache OpenServerless and Open Source marks
9. The three `<dialog>` panels (download / buy / contact) used by the pricing buttons

Rules for the conversion:

- Asset paths become absolute site paths (`images/…` → `/images/…`).
- `{% block title %}` / `{% block description %}` take the Trustant copy from
  `index1.html`'s `<head>`.
- Keep the inline `loading` first-paint gate script in `base.html`'s head.
- Drop the page-local `<style>` block that `landing.html` carries today: the
  landing styling now comes from the copied stylesheets.
- The page keeps its own `<header>`/`<footer>` markup **or** uses base's — see §3.

### 3. `templates/base.html` — shared chrome

Base currently carries ~600 lines of inline CSS implementing the old ink/paper
Trustable design system, plus the header and footer. The landing CSS is a
different, complete design system (`theme-light` on `<html>`, `--colors`
variables, LaunchKit components).

Approach: **base adopts the landing design system** and the inline palette is
replaced by links to the copied stylesheets, so the homepage, docs, architecture
and apps pages all read as one site.

Note that the Trustant style is a **dark terracotta theme**: `css/trustant.css`
overrides the LaunchKit tokens (including on `.theme-light`, which is why the
class name says "light" while the page renders dark). The documentation pages'
inline CSS is light ink-on-paper, so it has to be retargeted onto the new tokens
or it renders dark text on a dark ground.

- `<html lang="en" class="theme-light">`
- Head: link `css/index.css`, `pricing.css`, `tablet.css`, `mobile.css`,
  `trustant.css`, Font Awesome `all.min.css`; preload `InterVariable.woff2`;
  `defer` `/js/main.js`. Drop the Google Fonts `<link>`s — fonts are local now.
- Favicon: `/favicon/icon.svg`, `/favicon/favicon.ico`, apple-touch-icon.
- Keep the inline `<style>` only for the rules the docs pages still need that
  the landing CSS does not provide (`.gallery*`, `.eyebrow`, `.grid-paper`,
  `.prose`), retargeted onto the landing colour variables.
- Header becomes the landing `nav-container` markup: brand logo + `nav-menu` +
  hamburger toggle (`data-mobile-toggle` / `data-navigation`, driven by the
  copied `main.js`).
- Footer becomes the landing `footer-menu` markup, with the Trustant wordmark
  and the link list rebuilt from `get_section` so a renamed section still fails
  the build rather than leaving a dead link.

### 4. Logo replacement

Every occurrence of the Trustable mark becomes the Trustant mark:

- `templates/base.html:11` favicon `/trustable-logo.svg` → `/favicon/icon.svg`
- `templates/base.html:695` header `/logo-trustable.png` → `/images/logo-trustant.png`
- `templates/base.html:726` footer ditto, alt text `Trustable` → `Trustant`
- `templates/landing.html` hero logo ditto
- `alt` text and the surrounding template comments updated to say Trustant

Nuvolaris keeps its own mark (`/logo-nuvolaris.svg`), used for the Nuvolaris
nav item and the footer copyright.

### 5. Menu

The header nav becomes exactly, in this order:

| Label | Target |
| --- | --- |
| Documentation | `content/documentation/` section |
| Architecture | `content/architecture/` section |
| Templates | `content/apps/` section, **renamed** |
| OpenSource | the home page's `#credits` section, reached by a slow scroll |
| GitHub | `https://github.com/trustant/trustant` (icon + label, new window) |
| Nuvolaris | `https://nuvolaris.io`, shown as the Nuvolaris logo |

"Templates" is a rename of the existing Apps section, done via
`content/apps/_index.md` front matter:

```toml
title = "Templates"
[extra]
nav_title = "Templates"
```

The URL stays `/apps/` — the rename is the label, not the route, so no links
break. Section headings and the gallery titles follow the new `title`.

Home is reached through the brand logo at the left of the bar, so the bar
carries no separate "Trustant" item beside it — that would name the same
destination twice.

### OpenSource

The item scrolls to the open source credits at the foot of the home page.
Because that section exists only there, the link is an absolute `/#credits`
rather than a bare fragment: from a documentation page the browser navigates
home and lands on the section through a `scroll-margin-top` that clears the
floating bar.

When the section is already on the page, `handleSlowScroll()` in `main.js`
takes the click over and animates the travel itself. Native smooth scrolling is
both faster than wanted here and not tunable, so the glide is hand-animated
over 2.4s on a cubic ease-in-out. It honours `prefers-reduced-motion` by
jumping straight to the target, and writes `#credits` into the address bar
either way so the position stays shareable and Back behaves normally.

The bar is split in two: the four section links sit with the brand on the
left, and the two outbound destinations (GitHub, Nuvolaris) are pushed to the
right edge, so where the site goes and where it links out to read as separate
groups. The split is scoped above 1199px, where tablet.css turns the menu into
a dropdown — below that the items stack and an auto margin would push GitHub
down the panel rather than across it. The footer link list does keep its own "Trustant" entry,
where no logo sits next to it.

### 6. LinkedIn

`templates/base.html:778`:
`https://www.linkedin.com/showcase/trustable-ai/` →
`https://linkedin.com/showcase/trustant`

### 7. `config.toml`

- `title = "Trustant"`
- `description` — the Trustant positioning line from `index1.html`
- `base_url` — left as `https://trustable.it` for now; changing it moves the
  published site and is a separate, deliberate step. Flagged, not done.

## Fixes made while implementing

Recorded here because each was a defect the conversion exposed rather than a
step of the plan:

- **Nuvolaris nav wordmark invisible.** `logo-nuvolaris.svg` is already light
  artwork — unlike `logo-trustant.png`, which the theme inverts — so inverting
  it painted it dark-on-dark. It is shown unfiltered, as the "Powered by
  Nuvolaris" block shows the same file.
- **Hidden tab panels reserved grid rows.** `.gallery` is a grid, so its
  children are grid items, and `display: grid` on the container means the
  `hidden` attribute the tabs script sets no longer implies `display: none`.
  Every unselected group went on holding a row, stranding the selected tiles
  above several empty ones. Fixed with an explicit `.gallery-group[hidden]`
  rule in base.html. This was latent in the old site too.
- **Footer links all accent-orange.** The template paints every `<a>` in the
  accent, which turned the footer's two navigation columns into a block of
  solid orange. They are set as quiet text that comes up on hover.
- **Obsolete Trustable artwork removed.** The 18 brand files at the root of
  `static/` (`logo-trustable.png`, `trustable-anim.mp4`, `trustable-machines.png`
  and the rest) belonged to the old home page. Nothing references them after
  the conversion, and they were being republished on every build, so they are
  deleted.

## Out of scope

- The body prose of the ~25 markdown files under `content/documentation/`,
  `content/architecture/` and `content/apps/` still calls the product
  "Trustable". Renaming the product throughout the documentation text is an
  editorial pass, not part of this refactor.
- `base_url` / the published domain (see §7).
- Wiring up payment in the buy dialog — it collects details and stops, exactly
  as in `index1.html`.

## Verification

- `./build.sh --fast` serves the site with no Zola template or link errors.
- Home, `/documentation/`, `/architecture/`, `/apps/` and one app page all
  render with the new chrome.
- No `logo-trustable` or `trustable-logo` reference survives in `templates/`.
- The nav shows the six items above, with the logo as the link home; the
  hamburger works below the tablet breakpoint.
- OpenSource glides to the credits section over 2.4s, lands with the section
  clear of the floating bar, and jumps instead under reduced motion.

### Verified

`./build.sh build --fast` builds 34 pages with no template or link errors, and
every local asset referenced by the home, documentation, architecture and
Templates pages resolves in `docs/`. Rendered and checked in Chrome: the home
page (all nine sections, dark terracotta theme, tabbed gallery), the
documentation index, the Templates index, an application page, and the home
page at a 390px viewport (hamburger shown, no horizontal overflow).
