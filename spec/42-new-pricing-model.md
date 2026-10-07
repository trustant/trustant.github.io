# Spec 42 — New pricing model: Community, Desktop, Server, Cluster

Status: implemented on branch `spec-42`.

## Why

The three tiers on the home page (Personal free, Developer $100/month,
Enterprise $1,000/month) are replaced by four, which separate the free paths
(build it yourself, or download the desktop app) from the paid licences
(one server, or a cluster).

## The new tiers

| Tier | Price | What you get |
|---|---|---|
| **Trustant Community** | Open Source (free) | Build and install from source yourself. Community support. |
| **Trustant Desktop** | Free download; **$99/year** maintenance | Desktop app for Windows and Mac. The maintenance subscription enables updates, which ship continuously, and email support. |
| **Trustant Server** | **$99/month** or **$999/year** | Publish all your applications to ONE server, licence bound to one IP (internal ones too). SSL certificate included, even on a private intranet. `.deb` package for Ubuntu/Debian. Email or chat support. |
| **Trustant Cluster** | Contact sales | Everything in Server (publishing, internal IPs, SSL even on intranet, `.deb` for Ubuntu/Debian), on a cluster: HA, so it keeps running when a server goes down. Monitoring and backup. Email + chat + phone support. |

## Plan

`templates/landing.html`, `#pricing`:

- Heading: "Start Personal. Grow to a Private Cluster." becomes
  "Start Free. Grow to a Private Cluster."
- Switch the grid from `columns-3` to `columns-4` (already defined in
  `static/css/trustant.css`: 4 across, 2 under 1056px, 1 on mobile).
- Four `feature-card`s, in the order above:
  - **Community** — title "Trustant Community", price line "Open Source";
    build from source, self-hosted Apache OpenServerless,
    community support. Button "Source on GitHub"
    (tertiary), linking to https://github.com/trustant/trustant.
  - **Desktop** — "Free" with "+ $99/year maintenance" as the secondary line;
    installer for Windows and Mac, updates with active maintenance. Button
    "Download" (tertiary) opening `download-dialog`.
  - **Server** — "$99/month" with "or $999/year" as the secondary line; one
    server, licence bound to one IP, self-installed, email support. Marked
    `highlighted`, button "Buy" (primary) opening `buy-dialog`.
  - **Cluster** — "Contact sales"; licence for clusters. Button
    "Contact Sales" (tertiary) opening `contact-dialog`.
- Dialogs: rename "Trustant Personal" → "Trustant Desktop" in
  `download-dialog`; `buy-dialog` becomes "Trustant Server" with
  "$99/month or $999/year"; `contact-dialog` becomes "Trustant Cluster" and
  drops the $1,000/month figure.
- FAQ "Is there a free option?": name both free paths — Community, the open source edition (from
  source, community support) and Desktop (free download, maintenance optional).

## Decisions (defaults taken when implementing)

- The open source credits box from spec 41 stays after the prices: the card
  sells the tier, the box credits the projects and their licences.
- Desktop without maintenance keeps working on the version downloaded; the
  card says only that maintenance enables the updates.
- Card bullets were then set by the user as listed in the table (Desktop:
  "Email Support (with maintenance)"; Server and Cluster: their full lists).

## Verification

`./build.sh serve --fast`: four cards in one row on desktop, 2×2 on tablet,
stacked on mobile; every button opens the right dialog or link; no page still
mentions Personal, Developer, Enterprise, $100 or $1,000.
