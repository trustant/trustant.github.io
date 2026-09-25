#!/bin/bash
# Regenerate the Trustable site and preview it — see spec/13-generate.md.
# Installs zola into ~/.local/bin when it is not already on PATH.
#
#   ./build.sh          regenerate the catalog and gallery, then serve a preview
#   ./build.sh serve    the same, said explicitly
#   ./build.sh build    regenerate, write docs/, and commit the result
#   ./build.sh push     the same, from main, then push to publish the site
#   ./build.sh [...] --fast   reuse the last catalog and images, skipping GitHub
#
# generator.py regenerates the catalog from the live GitHub API into
# static/index.json on every run, so the site can never be generated from a
# stale one. --fast trades that guarantee for speed while iterating locally: it
# reuses what the last full run left behind and needs neither the network nor
# `gh`. Only `push` pushes: what `./build.sh build` commits is published by the
# PR-and-merge process in CLAUDE.md, of which `./build.sh push` is the final
# step — it builds and commits on main, then pushes.
# NO_COMMIT=1 builds without committing.
set -e

ZOLA_VERSION="v0.19.2"
BIN_DIR="$HOME/.local/bin"
HERE="$(cd "$(dirname "$0")" && pwd)"

install_zola() {
  case "$(uname -s)" in
  Darwin) os="apple-darwin" ;;
  Linux) os="unknown-linux-gnu" ;;
  *)
    echo "unsupported OS: $(uname -s)" >&2
    exit 1
    ;;
  esac

  case "$(uname -m)" in
  arm64 | aarch64) arch="aarch64" ;;
  x86_64 | amd64) arch="x86_64" ;;
  *)
    echo "unsupported architecture: $(uname -m)" >&2
    exit 1
    ;;
  esac

  # zola ships no aarch64 linux build; that host uses the x86_64 tarball.
  if [ "$os" = "unknown-linux-gnu" ] && [ "$arch" = "aarch64" ]; then
    arch="x86_64"
  fi

  tarball="zola-${ZOLA_VERSION}-${arch}-${os}.tar.gz"
  url="https://github.com/getzola/zola/releases/download/${ZOLA_VERSION}/${tarball}"

  echo ">> installing zola ${ZOLA_VERSION} into ${BIN_DIR}"
  mkdir -p "$BIN_DIR"
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  curl -fsSL "$url" -o "$tmp/$tarball"
  tar -xzf "$tmp/$tarball" -C "$tmp"
  mv "$tmp/zola" "$BIN_DIR/zola"
  chmod +x "$BIN_DIR/zola"
}

ZOLA="$(command -v zola || true)"
if [ -z "$ZOLA" ]; then
  if [ -x "$BIN_DIR/zola" ]; then
    ZOLA="$BIN_DIR/zola"
  else
    install_zola
    ZOLA="$BIN_DIR/zola"
  fi
fi

echo ">> using $("$ZOLA" --version) at $ZOLA"

cd "$HERE"

MODE="serve"
FAST=""
for arg in "$@"; do
  case "$arg" in
  serve | build | push) MODE="$arg" ;;
  --fast) FAST=1 ;;
  *)
    echo "usage: $0 [serve|build|push] [--fast]" >&2
    exit 1
    ;;
  esac
done

# `push` is `build` plus a precondition and a follow-up: it falls through the
# same generation, zola and commit steps below, then pushes. The precondition is
# checked here, before any of that work, so a wrong-branch run fails in a second
# rather than after a full catalog fetch.
if [ "$MODE" = "push" ]; then
  # A build committed on a feature branch never reaches the site, and the
  # working tree looks identical either way — so refuse rather than publish
  # from the wrong place. No checkout is attempted: it can fail on a dirty tree
  # and switching branches under the caller is the caller's call.
  BRANCH="$(git symbolic-ref --quiet --short HEAD || true)"
  if [ "$BRANCH" != "main" ]; then
    echo "error: push builds from main; you are on ${BRANCH:-a detached HEAD}" >&2
    echo "       run: git checkout main" >&2
    exit 1
  fi

  # Nothing would be committed, so there would be nothing to publish.
  if [ -n "${NO_COMMIT:-}" ]; then
    echo "error: NO_COMMIT is incompatible with push" >&2
    exit 1
  fi
fi

# --fast reuses the catalog and images from the last full run instead of asking
# GitHub for them again: generator.py --offline reads static/index.json back and
# leaves static/images/ alone. It still regenerates every page, so a template or
# a spec change is picked up — only the network work is skipped. Use it while
# iterating; a publishing build should be a full one, or the site is generated
# from whatever the organization looked like the last time someone ran it.
if [ -n "$FAST" ]; then
  echo ">> --fast: reusing the catalog and images from the last full run"
  ./generator.py --offline
else
  # generator.py talks to the GitHub API with `gh`, so a missing or unauthorized
  # CLI is the build's problem now rather than the support submodule's. Say so
  # here instead of failing deep inside the generator. --fast needs neither, so
  # this is checked only on the path that does.
  if ! command -v gh >/dev/null 2>&1; then
    echo "error: the gh CLI is required to build the catalog — https://cli.github.com" >&2
    echo "       (or rebuild from the last catalog with: $0 $MODE --fast)" >&2
    exit 1
  fi
  if ! gh auth status >/dev/null 2>&1; then
    echo "error: gh is not authenticated — run: gh auth login" >&2
    echo "       (or rebuild from the last catalog with: $0 $MODE --fast)" >&2
    exit 1
  fi

  # One step: fetch the catalog from the live GitHub API, download every image
  # the site shows, and generate the gallery. A failure here stops the build
  # rather than falling back to a stale catalog.
  echo ">> generating the catalog and the Apps gallery"
  ./generator.py
fi

# `serve` previews on http://127.0.0.1:1111 with live reload and incremental
# rebuilds, and does NOT write docs/. The port is pinned so the URL is
# predictable; zola would otherwise drift to a free one.
if [ "$MODE" = "serve" ]; then
  echo ">> preview on http://127.0.0.1:1111 (ctrl-c to stop)"
  exec "$ZOLA" serve --port 1111
fi

# Zola wipes its output dir, so CNAME and .nojekyll are re-published from
# static/ on every build rather than being kept in docs/ by hand.
"$ZOLA" build --output-dir docs --force

echo ">> built $(find docs -name '*.html' | wc -l | tr -d ' ') pages into docs/"

# The generated home page is published at /index1.html, and the placeholder at
# the repo root takes its place at /index.html — so the site shows "Coming
# soon" while the real page is built, reviewed and reachable at its own URL.
# See spec/31-coming-soon.md.
#
# This runs after zola, which wipes and rewrites docs/ on every build, so the
# swap has to be reapplied each time rather than being kept in docs/ by hand.
# `serve` has already exec'd away above, so previewing still shows the real
# home page at / and is unaffected.
if [ ! -f index.html ]; then
  echo "error: index.html (the placeholder home page) is missing" >&2
  exit 1
fi
mv docs/index.html docs/index1.html
cp index.html docs/index.html
echo ">> published the real home page at /index1.html, placeholder at /index.html"

# Commit what the build owns. Confined to these paths so an unrelated edit
# sitting in the working tree is never swept into the build's commit, and
# skipped entirely when they come back unchanged. Only `push` goes on to
# publish; for `build`, publishing stays a separate, deliberate step.
if [ -n "${NO_COMMIT:-}" ]; then
  echo ">> NO_COMMIT set, leaving changes in the working tree"
  exit 0
fi

# A commit on a detached HEAD is unreachable from any branch, so don't make one.
if ! git symbolic-ref --quiet HEAD >/dev/null 2>&1; then
  echo ">> detached HEAD, leaving changes in the working tree"
  exit 0
fi

# The catalog and the images the generator downloaded are committed here now,
# so the published site serves both from trustable.it.
BUILD_PATHS=(content/apps static/index.json static/images docs)

# --porcelain over these paths alone reports both tracked edits and untracked
# new files (a newly added application page or icon) without touching the
# index, so a caller who had something else staged still has it staged if
# there turns out to be nothing to do.
if [ -z "$(git status --porcelain -- "${BUILD_PATHS[@]}")" ]; then
  # Not an error: the site may already be up to date and there can still be
  # earlier local commits for `push` to publish.
  echo ">> no changes to commit"
else
  # `commit --only <paths>` commits exactly these paths and leaves anything else
  # staged untouched, but it will not pick up untracked files, so add first.
  # The -m flags must precede `--`; everything after it is taken as a pathspec.
  git add -- "${BUILD_PATHS[@]}"
  git commit --quiet --only \
    -m "Rebuild the site" \
    -m "Regenerated the catalog into static/index.json, downloaded the application images into static/images/, regenerated the Apps gallery and rebuilt docs/ with zola. Committed by build.sh." \
    -- "${BUILD_PATHS[@]}"
  echo ">> committed $(git rev-parse --short HEAD)"
fi

if [ "$MODE" != "push" ]; then
  exit 0
fi

# Publishing: the docs commit is already made, so this is what puts the rebuilt
# site on GitHub Pages. A rejected push means origin/main has moved ahead —
# report it and stop rather than force-pushing or rebasing behind the user's
# back, which is theirs to resolve.
echo ">> pushing main to origin"
if ! git push origin main; then
  echo "error: push rejected — origin/main has moved ahead" >&2
  echo "       reconcile it yourself (e.g. git pull --rebase), then re-run" >&2
  exit 1
fi
echo ">> pushed $(git rev-parse --short HEAD)"

