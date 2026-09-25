#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Generate the Trustable catalog and the Apps gallery.

See spec/13-generate.md. This is the only script the site build runs, and the
only thing that talks to the GitHub API — with `gh`, so it uses the
maintainer's credentials and rate limit.

It does three things:

1. **Builds the catalog** from the trustable-ai organization, the logic
   described in spec/8-index.md and previously living in support/index.py: an
   application starter is a public repository whose description begins with
   "Trustable:", carrying <key>=<value> parameters (currently only templates=)
   which are stripped from the human-readable text. Applications are read from
   the _index.md of the templates repository, each line linking the
   application's own repository, and grouped by its first "# " heading.
2. **Downloads every image** the site shows into static/images/, named after
   the repository it came from, so the published site reaches nothing but its
   own origin.
3. **Writes the gallery**: Zola sections under content/apps/<group>/, each page
   built from the application repository's README, plus the catalog itself at
   static/index.json — served as https://trustable.it/index.json.

support/index.py still publishes the upstream index.json read by Trustable
itself; it is a separate consumer and this script does not touch it.

Usage:
    ./generator.py             # fetch the catalog, then generate
    ./generator.py --offline   # reuse static/index.json and the clones
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTENT = HERE / "content" / "apps"
STATIC = HERE / "static"
# The catalog this site publishes, served at <base_url>/index.json.
# With --offline it is the input instead of the output.
INDEX = STATIC / "index.json"
# Every image the site shows, downloaded so a page reaches only our own origin.
# Wholly owned by this script: clean_images() deletes anything here it did not
# just write, so no hand-written file belongs in it.
IMAGES = STATIC / "images"
# The clones must stay outside content/: zola parses everything under it and a
# repo's bare README has no front matter, which fails the build.
WORK = HERE / ".templates"

ORG = "trustable-ai"

# The site's canonical domain. The published catalog carries absolute URLs so a
# consumer reading it from anywhere can resolve an icon without knowing where
# the file came from; the generated pages keep the site-absolute path, which
# resolves under a local preview too.
#
# Read from config.toml rather than repeated here: this and base_url have to
# name the same origin, and when they were two hardcoded copies a domain change
# updated one and left the catalog publishing icon URLs on the old host.
def _site_from_config():
    with open(HERE / "config.toml", "rb") as handle:
        base = tomllib.load(handle).get("base_url", "")
    return base.rstrip("/")


SITE = _site_from_config()

# The marker a repository's GitHub description begins with to be part of the
# catalog. Not to be confused with MARKER below, which stamps generated files.
DESCRIPTION_MARKER = "trustable:"

RAW_BASE = "https://raw.githubusercontent.com/{repo}/refs/heads/main/{path}"
RAW_PREFIX = "https://raw.githubusercontent.com/"
APPLICATION_INDEX = "_index.md"

# An application's icon, published by the application's own repository. This is
# the file ./screenshot.sh stages in a workbench, so an application ships its
# own image and the templates repository holds none.
APPLICATION_SCREENSHOT = "screenshot.png"

# An application's own repository, taken from what its _index.md line links to:
# a full https://github.com/<owner>/<name> URL, a bare <owner>/<name> slug, or
# the legacy "<name>.md" resolved against ORG. See parse_repo.
GITHUB_URL = "https://github.com/"

# Convention for a marked repository that carries no templates=: its
# applications live in a sibling repository with this suffix.
TEMPLATES_SUFFIX = "-templates"

# <key>=<value> tokens carried in the description. A bare value is
# whitespace-delimited; a "quoted" one may contain spaces, so a parameter is not
# limited to single-word values.
KEY_VALUE = re.compile(r"""\b([A-Za-z][A-Za-z0-9_-]*)=(?:"([^"]*)"|(\S+))""")

# Same shape trustable-app accepts for notebook.repository: owner/repository.
REPO_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

# One application per line: "- [<title>](<target>) <description>", where
# <target> names the repository — see parse_repo. The description is optional;
# anything else in the file is ignored.
#
# Only a "-" or "*" bullet counts. An ordered list is deliberately not a list
# here: renumbering a group's entries to "1." is how a templates repository
# takes them out of the catalog without deleting them, so widening this to
# accept "1." would silently republish every disabled entry.
APPLICATION_LINE = re.compile(r"^\s*[-*]\s*\[([^\]]+)\]\(([^)\s]+)\)\s*(.*)$")

# The group name is the first top-level "# " heading of an _index.md.
GROUP_HEADING = re.compile(r"^#\s+(.*\S)\s*$")

# Written into every generated file; a directory whose _index.md carries it is
# ours to delete and rewrite, anything else under content/apps/ is
# hand-written and left alone.
MARKER = "generated by generator.py — see spec/13-generate.md"

# A README that is only the workspace stub carries no information about the
# application, so such a page falls back to the catalog description instead.
STUB_READMES = {"# trustable workspace"}


# ---------------------------------------------------------------------------
# The catalog — see spec/8-index.md
# ---------------------------------------------------------------------------


def run(args):
    """Run a command and return stdout, failing loudly."""
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"error: {' '.join(args)} failed:\n{result.stderr.strip()}")
    return result.stdout


def normalize_templates(value):
    """Normalize a templates= value to owner/repository.

    Accepts a bare owner/repo or a full GitHub URL. Returns None when the value
    cannot be understood, which disqualifies the repository as a starter.
    """
    value = (value or "").strip()
    for prefix in ("https://github.com/", "http://github.com/"):
        if value.lower().startswith(prefix):
            value = value[len(prefix):]
            break
    if "://" in value:
        return None
    value = value.strip("/")
    if value.endswith(".git"):
        value = value[: -len(".git")]
    parts = value.split("/")
    if len(parts) != 2 or not all(REPO_SEGMENT.match(part) for part in parts):
        return None
    return f"{parts[0]}/{parts[1]}"


def raw_url(repo, path):
    """URL of a file on the main branch of repo, as raw.githubusercontent.com."""
    return RAW_BASE.format(repo=repo, path=path.lstrip("/"))


def fetch_file(repo, path):
    """Fetch a file from a repository, returning None when it is not published.

    Read through `gh` rather than raw.githubusercontent.com. Both serve the
    same bytes, but the raw host is anonymous and rate-limits hard enough to
    fail a build (429 after a few dozen requests), while `gh` carries the
    maintainer's 5000/hour credentials — which this script already depends on
    for the repository listing. The raw host stays as a fallback for the case
    where `gh` cannot answer at all.
    """
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/contents/{path.lstrip('/')}",
         "--header", "Accept: application/vnd.github.raw"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        return result.stdout
    if "404" in result.stderr or "Not Found" in result.stderr:
        return None

    url = raw_url(repo, path)
    print(f"   ! gh could not read {repo}/{path}, trying {url}", file=sys.stderr)
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        sys.exit(f"error: GET {url} failed: {error.code} {error.reason}")
    except urllib.error.URLError as error:
        sys.exit(f"error: GET {url} failed: {error.reason}")


def repo_exists(repo):
    """Whether owner/repository exists on GitHub, via the gh CLI.

    An anonymous HEAD on github.com cannot tell a missing repository from a
    private one, and both matter here: an application whose repository is
    private is as unusable to a user as one that was never created. `gh` is
    already a dependency and carries the maintainer's credentials, so it sees
    private repositories of the organization too.

    Returns True when the repository exists, False on a definite 404, and None
    when the answer is unknown (gh missing, not authenticated, network down) so
    a broken environment produces no misleading "does not exist" warnings.
    """
    result = subprocess.run(["gh", "api", f"repos/{repo}"],
                            capture_output=True, text=True)
    if result.returncode == 0:
        return True
    if "404" in result.stderr or "Not Found" in result.stderr:
        return False
    return None


def parse_repo(target):
    """Resolve an _index.md link target to the owner/name it points at.

    The link is the application's repository, given either way round:

    - "https://github.com/trustable-ai/tetris" — a full URL, so an application
      may live under any owner and need not be named after its link.
    - "trustable-ai/tetris" — the same thing as a bare slug.
    - "tetris.md" or "tetris" — the older convention, where the link named a
      markdown file beside the _index.md and the repository was assumed to be
      ORG/<stem>. Still resolved that way, so existing files keep working.

    A trailing "/" or ".git" is dropped. Returns None for anything else — an
    off-GitHub URL, a path with directories, a segment GitHub would not accept —
    so the caller can skip the line and say why.
    """
    value = (target or "").strip()
    if not value:
        return None
    lowered = value.lower()
    for prefix in ("https://github.com/", "http://github.com/"):
        if lowered.startswith(prefix):
            value = value[len(prefix):]
            break
    else:
        if "://" in value:
            return None
    value = value.strip("/")
    if value.endswith(".git"):
        value = value[: -len(".git")]
    parts = value.split("/")
    if len(parts) == 1:
        # The legacy form: a markdown file beside the _index.md naming a repo
        # in our own organization.
        parts = [ORG, parts[0][: -len(".md")] if parts[0].endswith(".md")
                 else parts[0]]
    if len(parts) != 2 or not all(REPO_SEGMENT.match(part) for part in parts):
        return None
    return f"{parts[0]}/{parts[1]}"


def parse_applications(text, source=None):
    """Parse a templates _index.md into (group, applications).

    The group is the first "# " heading with the marker removed; it is None
    when the file has none.

    A line "- [<title>](<target>) <description>" yields all three fields: the
    link target names the application's repository — see parse_repo — the link
    text is the human-readable "title" and the trailing prose the
    "description". "name" is the repository's own name, which is the page's
    filename and its sort key. The icon is the screenshot.png published by that
    same repository, which is what ./screenshot.sh stages, so an application
    carries its own image instead of the templates repository holding one per
    entry.

    `source` is the repository the listing came from, used only to say which
    file a skipped line was in.
    """
    group = None
    applications = []
    for line in (text or "").splitlines():
        if group is None:
            heading = GROUP_HEADING.match(line)
            if heading:
                group = " ".join(heading.group(1).split()) or None
        match = APPLICATION_LINE.match(line)
        if not match:
            continue
        title, target, description = match.groups()
        repo = parse_repo(target)
        if repo is None:
            where = f"{source}/{APPLICATION_INDEX}" if source else APPLICATION_INDEX
            print(f"   ! {where}: skipping {title.strip()} — "
                  f"{target} is not a repository", file=sys.stderr)
            continue
        applications.append({
            "name": repo.split("/")[1],
            "title": " ".join(title.split()),
            "repo": GITHUB_URL + repo,
            "icon": raw_url(repo, APPLICATION_SCREENSHOT),
            "description": " ".join(description.split()),
        })
    return group, applications


def parse_description(description):
    """Split "Trustable: <text>" into (text, params).

    Returns (None, None) when the description does not carry the marker, which
    is how non-starter repositories are filtered out.
    """
    trimmed = (description or "").strip()
    if trimmed[: len(DESCRIPTION_MARKER)].lower() != DESCRIPTION_MARKER:
        return None, None
    rest = trimmed[len(DESCRIPTION_MARKER):]
    # Only one of the two value groups matches; the other is the empty string.
    params = {key.lower(): quoted or bare
              for key, quoted, bare in KEY_VALUE.findall(rest)}
    text = " ".join(KEY_VALUE.sub(" ", rest).split())
    return text, params


def fetch_repositories():
    """List the org's public repositories with the gh CLI."""
    output = run([
        "gh", "api", "--paginate",
        f"orgs/{ORG}/repos?type=public&per_page=100",
    ])
    # --paginate concatenates one JSON array per page when the output is piped
    # through jq; without jq it returns a single stream of arrays. Decode
    # defensively so both shapes work.
    decoder = json.JSONDecoder()
    repositories = []
    position = 0
    while position < len(output):
        while position < len(output) and output[position].isspace():
            position += 1
        if position >= len(output):
            break
        page, position = decoder.raw_decode(output, position)
        repositories.extend(page)
    return repositories


def build_starters(repositories):
    """Build the starter list and the applications each one's templates offer.

    A repository with a usable templates= is a starter, and its applications
    come from the templates repository. A repository carrying the marker
    *without* templates= is not a starter but still contributes applications,
    read from the conventional <name>-templates repository and falling back to
    the repository itself — that is how a plain collection of applications is
    published without offering a starter.

    A repository whose _index.md is absent contributes no applications.

    Applications are grouped under the first "# " heading of the _index.md they
    came from. Two repositories sharing a heading share the group.
    """
    starters = []
    groups = {}
    for repo in repositories:
        if repo.get("private") or repo.get("archived") or repo.get("disabled"):
            continue
        text, params = parse_description(repo.get("description"))
        if text is None:
            continue
        name = (repo.get("name") or "").strip()
        full_name = (repo.get("full_name") or "").strip() or f"{ORG}/{name}"
        if not name:
            continue
        templates = normalize_templates(params.get("templates"))
        if templates:
            starters.append({
                "name": name,
                "repo": full_name,
                "templates": templates,
                "description": text,
            })
        else:
            print(f"   {full_name}: no templates=, applications only",
                  file=sys.stderr)
        # Without templates= the applications live in the conventional
        # <name>-templates repository, falling back to the repository itself.
        source = templates or f"{full_name}{TEMPLATES_SUFFIX}"
        listing = fetch_file(source, APPLICATION_INDEX)
        if listing is None and not templates:
            source = full_name
            listing = fetch_file(source, APPLICATION_INDEX)
        if listing is None:
            print(f"   {source}: no {APPLICATION_INDEX}", file=sys.stderr)
            continue
        group, entries = parse_applications(listing, source)
        if entries and group is None:
            group = name
            print(f"   {source}: no '# ' heading, grouping under {group}",
                  file=sys.stderr)
        for entry in entries:
            groups.setdefault(group, []).append(entry)
    starters.sort(key=lambda item: item["name"])
    applications = {
        group: sorted(entries, key=lambda item: (item["title"], item["name"]))
        for group, entries in sorted(groups.items())
    }
    return starters, applications


def check_repositories(applications, checkouts):
    """Warn about applications whose repository could not be had.

    The repository is a convention derived from the template name linked in
    _index.md, so a typo there — or a template listed before its repository was
    created — points at nothing. Like a missing image this is a warning and not
    an error: the entry stays in the catalog and the repository can be created
    later.

    A repository that did not clone is reported here too rather than warned
    about separately, so one broken application produces one warning. Each
    distinct repository is probed once, since the same template may be listed
    by more than one _index.md.
    """
    urls = sorted({app["repo"] for entries in applications.values()
                   for app in entries})
    verdicts = {}
    for url in urls:
        repo = url.removeprefix("https://github.com/").rstrip("/")
        # A repo that cloned exists; only ask GitHub about the ones that did not.
        verdicts[url] = True if checkouts.get(repo) else repo_exists(repo)
    missing = {url for url, exists in verdicts.items() if exists is False}
    unknown = {url for url, exists in verdicts.items() if exists is None}
    seen = set()
    for entries in applications.values():
        for app in entries:
            if app["repo"] in missing and app["repo"] not in seen:
                seen.add(app["repo"])
                print(f"   ! no repository for {app['title']} — {app['repo']}",
                      file=sys.stderr)
    if unknown:
        print(f"   ! could not check {len(unknown)} repositories "
              f"(is gh authenticated?)", file=sys.stderr)
    return missing


# ---------------------------------------------------------------------------
# Images — downloaded so the published site reaches only its own origin
# ---------------------------------------------------------------------------


def image_name(repo, path):
    """Name of the local copy of <path> in <repo>: '<owner>-<repo>[-<path>]'.

    The screenshot at the repository root is the icon and by far the common
    case, so it drops the path and is simply '<owner>-<repo>.png'. Any other
    image keeps its path in the name, so a README's second illustration cannot
    collide with the screenshot or with another repository's.
    """
    path = path.lstrip("./")
    stem = re.sub(r"[^a-z0-9]+", "-", repo.lower()).strip("-")
    extension = Path(path).suffix or ".png"
    if path != APPLICATION_SCREENSHOT:
        slug_path = re.sub(r"[^a-z0-9]+", "-", str(Path(path).with_suffix("")).lower())
        stem = f"{stem}-{slug_path.strip('-')}"
    return stem + extension


def split_raw(url):
    """Split a raw.githubusercontent.com URL into (repo, path).

    Returns (None, None) for anything else: an image deliberately hosted
    somewhere other than GitHub is not ours to copy.
    """
    if not url.startswith(RAW_PREFIX):
        return None, None
    parts = url[len(RAW_PREFIX):].split("/")
    # <owner>/<repo>/refs/heads/<branch>/<path...>
    if len(parts) >= 6 and parts[2] == "refs" and parts[3] == "heads":
        return f"{parts[0]}/{parts[1]}", "/".join(parts[5:])
    # <owner>/<repo>/<branch>/<path...>
    if len(parts) >= 4:
        return f"{parts[0]}/{parts[1]}", "/".join(parts[3:])
    return None, None


def local_image(repo, path, checkouts, used, offline):
    """Copy an image into static/images/ and return its site-absolute path.

    The application repo is already cloned for its README, so the file is
    normally taken from the checkout and a build does no extra network I/O.
    Only a file missing from the clone is fetched, and only when online.

    Returns None when the image cannot be had, which leaves the entry with no
    icon rather than a link to nothing.
    """
    name = image_name(repo, path)
    target = IMAGES / name
    url = f"/images/{name}"
    if name in used:
        return url

    source = checkouts.get(repo)
    candidate = source / path if source else None
    if candidate is not None and candidate.is_file():
        IMAGES.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(candidate, target)
        used.add(name)
        return url

    # Not in the clone. An already-downloaded copy stands in when offline, so a
    # network-free rebuild keeps the images the previous run fetched.
    if offline:
        if target.is_file():
            used.add(name)
            return url
        print(f"   ! {repo}: no {path} in the clone and --offline given",
              file=sys.stderr)
        return None

    # Through `gh` for the same reason fetch_file() does: the anonymous raw
    # host rate-limits hard enough to fail a build. --raw keeps the bytes
    # untouched, so an image survives the round trip.
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/contents/{path.lstrip('/')}",
         "--header", "Accept: application/vnd.github.raw"],
        capture_output=True,
    )
    if result.returncode == 0:
        payload = result.stdout
    else:
        try:
            with urllib.request.urlopen(raw_url(repo, path), timeout=30) as response:
                payload = response.read()
        except (urllib.error.URLError, OSError) as error:
            reason = getattr(error, "reason", error)
            print(f"   ! {repo}: cannot fetch {path} — {reason}", file=sys.stderr)
            return None
    IMAGES.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    used.add(name)
    return url


def keep_image(url, used):
    """Claim an already-downloaded image named by a site-absolute /images/ path.

    Reading our own catalog back, an icon already names a file a previous run
    wrote. Marking it used is what stops clean_images() from deleting the very
    images that run is about to publish. A path naming a file that is no longer
    there yields None, so the entry loses its icon rather than pointing at a
    gap.
    """
    name = url[len("/images/"):]
    if not (IMAGES / name).is_file():
        print(f"   ! {url} is in the catalog but not in "
              f"{IMAGES.relative_to(HERE)}", file=sys.stderr)
        return None
    used.add(name)
    return url


# An icon this site published: the generator-owned /images/<file> tail, taken
# from the end of the URL whatever precedes it. The origin is whatever base_url
# was when that catalog was written, so it is deliberately not pinned to the
# current one — and matching the tail rather than a single leading origin also
# recovers a catalog left with stacked origins by an earlier buggy run.
OURS_IMAGE = re.compile(r"(/images/[^/]+)$")


def ours_image(url):
    """The site-absolute path of an icon we published, or None if not ours.

    The path alone is not proof — a foreign URL can end in /images/<file> too —
    so the file has to be one we actually hold. That is what separates our own
    catalog read back from a README hotlinking someone else's screenshot.
    """
    if not url:
        return None
    match = OURS_IMAGE.search(url)
    if not match:
        return None
    return match.group(1) if (IMAGES / match.group(1)[len("/images/"):]).is_file() else None


def clean_images(used):
    """Delete images no application referenced this run.

    Without this an application that leaves the catalog keeps its image
    published forever. The directory is generator-owned, so anything not just
    written is stale by definition.
    """
    if not IMAGES.is_dir():
        return 0
    removed = 0
    for child in sorted(IMAGES.iterdir()):
        if child.is_file() and child.name not in used:
            child.unlink()
            removed += 1
    return removed


# ---------------------------------------------------------------------------
# The gallery
# ---------------------------------------------------------------------------


def slug(text: str) -> str:
    """Group name to directory name: 'Utilities' -> 'utilities'."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def toml_str(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def app_repo(app: dict) -> str:
    """The <owner>/<name> the application's own repository lives at."""
    return app["repo"].removeprefix("https://github.com/").rstrip("/")


def clone(repo: str, offline: bool) -> Path | None:
    """Clone or refresh an application repo into its gitignored working copy."""
    WORK.mkdir(parents=True, exist_ok=True)
    dest = WORK / repo.split("/")[-1]
    if dest.exists():
        if not offline:
            subprocess.run(
                ["git", "-C", str(dest), "pull", "--quiet", "--ff-only"], check=False
            )
        return dest
    if offline:
        print(f"   ! {repo} not cloned and --offline given", file=sys.stderr)
        return None
    print(f"   cloning {repo}")
    result = subprocess.run(
        ["git", "clone", "--depth", "1", "--quiet", f"https://github.com/{repo}", str(dest)],
        check=False,
    )
    return dest if result.returncode == 0 else None


def body_for(checkout: Path | None) -> str:
    """Page body: the application repo's README.

    The *-templates repos are not read: their per-application markdown is the
    prompt an application was built from, not a description of it — see
    spec/12-readme.md.
    """
    if checkout is None:
        return ""
    readme = checkout / "README.md"
    return readme.read_text(encoding="utf-8") if readme.is_file() else ""


# A markdown image whose source is relative — anything not starting with a
# scheme, a protocol-relative //, or a site-absolute /.
RELATIVE_IMAGE = re.compile(r"(!\[[^\]]*\]\()(?!\w+:|//|/)([^)\s]+)")

# An absolute markdown image, so a README pointing straight at raw GitHub is
# localized like a relative one rather than left hotlinking.
ABSOLUTE_IMAGE = re.compile(r"(!\[[^\]]*\]\()(https?://[^)\s]+)")


def localize_images(body, repo, checkouts, used, offline):
    """Point the README's images at our own copies under /images/.

    A README illustrates itself with `![Title](screenshot.png)`, relative to the
    repository root. Rendered under /apps/<group>/<name>/ that resolves to
    nothing, so every relative source is copied into static/images/ and
    rewritten to the site-absolute path of that copy. A source already pointing
    at raw.githubusercontent.com is localized the same way; anything else
    absolute is deliberately hosted elsewhere and left alone.

    An image that cannot be had keeps its original source rather than becoming
    a link to nothing.
    """
    def relative(match):
        path = match.group(2).lstrip("./")
        url = local_image(repo, path, checkouts, used, offline)
        return match.group(1) + (url or match.group(2))

    def absolute(match):
        source_repo, path = split_raw(match.group(2))
        if not source_repo:
            return match.group(0)
        url = local_image(source_repo, path, checkouts, used, offline)
        return match.group(1) + (url or match.group(2))

    return ABSOLUTE_IMAGE.sub(absolute, RELATIVE_IMAGE.sub(relative, body))


# An image standing alone on its line, so removing it takes the whole line
# rather than leaving an empty paragraph behind.
STANDALONE_IMAGE = re.compile(r"^[ \t]*!\[[^\]]*\]\(\s*(\S+?)\s*(?:\s+[\"'][^\n]*)?\)[ \t]*$\n?", re.M)


def drop_icon_image(body: str, icon: str | None) -> str:
    """Remove the README's own copy of the screenshot page.html already shows.

    Every README opens by illustrating itself with the same screenshot the
    catalog points `icon` at, and page.html renders that icon as the page hero
    — so left alone the application's screenshot appears twice on the page.
    The hero is the one that stays: the gallery tile is built from the same
    field, so tile and page cannot drift apart.
    """
    if not icon:
        return body
    body = STANDALONE_IMAGE.sub(
        lambda m: "" if m.group(1) == icon else m.group(0), body
    )
    # Removing the line leaves the blank line above and below it adjacent;
    # collapse the run so the generated markdown reads as if it never existed.
    return re.sub(r"\n{3,}", "\n\n", body)


def app_key(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", title.lower())


def strip_title(body: str, title: str, name: str) -> str:
    """Drop a leading `# Title` that only restates the frontmatter title.

    Most copy opens with a step heading ('# 1 - Application Foundation') that
    is real content, so only a heading naming the application goes. The match
    is loose in one direction: 'Database Manager' under the title 'AI Database
    Manager' is the same name, so a heading contained in the title (or equal to
    the catalog name) counts, while a longer heading is left alone.
    """
    lines = body.lstrip().splitlines()
    if lines and lines[0].startswith("#"):
        heading = app_key(lines[0].lstrip("#").strip())
        if heading and (heading in app_key(title) or heading == app_key(name)):
            return "\n".join(lines[1:]).lstrip()
    return body.strip()


def clean_generated() -> None:
    """Remove previously generated group directories, keeping everything else."""
    for child in sorted(CONTENT.iterdir()):
        index = child / "_index.md"
        if child.is_dir() and index.is_file() and MARKER in index.read_text(encoding="utf-8"):
            shutil.rmtree(child)


def write_group(group, apps, weight, checkouts, used, offline):
    directory = CONTENT / slug(group)
    directory.mkdir(parents=True, exist_ok=True)
    directory.joinpath("_index.md").write_text(
        "+++\n"
        f"title = {toml_str(group)}\n"
        f"description = {toml_str(f'{group} you can start from, ready to run on your own infrastructure.')}\n"
        f"weight = {weight}\n"
        'sort_by = "weight"\n'
        'template = "section.html"\n'
        'page_template = "page.html"\n'
        "[extra]\n"
        f"generated = {toml_str(MARKER)}\n"
        "+++\n",
        encoding="utf-8",
    )

    written = 0
    for order, app in enumerate(apps, start=1):
        repo = app_repo(app)
        title = app.get("title") or app["name"]
        # The catalog points at the screenshot in the application's own repo;
        # the page shows our copy of it, so the site serves its own images.
        # Reading our own catalog back (--offline) the icon is already one of
        # ours, so it is only stripped back to the path the page wants — the
        # image it names is in static/images/ from the run that wrote it.
        #
        # Recognised by its /images/ path rather than by the origin in front of
        # it: a catalog written before a domain change still names our files,
        # and matching on SITE alone would take it for a foreign URL and paste
        # the new origin in front of the old one.
        icon = app.get("icon")
        ours = ours_image(icon)
        if ours:
            icon = keep_image(ours, used)
        elif icon:
            source_repo, path = split_raw(icon)
            icon = (local_image(source_repo, path, checkouts, used, offline)
                    if source_repo else icon)
        # The page keeps the site-absolute path, which resolves under a local
        # preview as well as in production; the published catalog gets the full
        # URL, since whatever reads it is not being served from this site.
        if icon:
            app["icon"] = SITE + icon
        else:
            app.pop("icon", None)
            print(f"   ! {repo} has no icon")
        body = strip_title(body_for(checkouts.get(repo)), title, app["name"])
        if body.strip().lower() in STUB_READMES or not body.strip():
            # Worth saying out loud: the page is now one line of catalog copy
            # because the repo has no usable README, not because it has none.
            print(f"   ! {repo} has no usable README, using the description")
            body = app.get("description", "")
        else:
            # Localize first, so the icon comparison is between like and like.
            body = drop_icon_image(
                localize_images(body, repo, checkouts, used, offline), icon
            )

        front = [
            "+++",
            f"title = {toml_str(title)}",
            f"description = {toml_str(app.get('description', ''))}",
            f"weight = {order * 10}",
            "[extra]",
            f"generated = {toml_str(MARKER)}",
            f"group = {toml_str(group)}",
            f"repo = {toml_str(app['repo'])}",
        ]
        if icon:
            front.append(f"icon = {toml_str(icon)}")
        front += ["+++", ""]

        directory.joinpath(f"{app['name']}.md").write_text(
            "\n".join(front) + body.strip() + "\n", encoding="utf-8"
        )
        written += 1
    return written


def catalog_content(text):
    """The parts of a catalog worth comparing — everything but `generated`."""
    try:
        document = json.loads(text)
        return document.get("starters"), document.get("applications")
    except (ValueError, AttributeError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="reuse static/index.json and the existing clones instead of "
             "fetching the catalog from GitHub",
    )
    args = parser.parse_args()

    previous = INDEX.read_text(encoding="utf-8") if INDEX.is_file() else ""

    if args.offline:
        if not previous:
            print(f"error: {INDEX.relative_to(HERE)} not found — --offline has "
                  "no catalog to reuse. Run without it once.", file=sys.stderr)
            return 1
        print(f">> reading {INDEX.relative_to(HERE)} (offline)")
        catalog = json.loads(previous)
        starters = catalog.get("starters", [])
        applications = catalog.get("applications", {})
        generated = catalog.get("generated", "")
    else:
        print(f">> fetching the catalog from the {ORG} organization")
        starters, applications = build_starters(fetch_repositories())
        generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Guard before anything is deleted: clean_generated() removes the existing
    # pages, so an API hiccup must not be allowed to blank the gallery.
    if not starters:
        print("error: no starters found — refusing to rebuild from an empty "
              "catalog", file=sys.stderr)
        return 1

    print(f">> {len(starters)} starters, "
          f"{sum(len(entries) for entries in applications.values())} "
          f"applications in {len(applications)} groups")
    for starter in starters:
        print(f"   {starter['name']:<16} {starter['repo']:<32} "
              f"templates={starter['templates']}")

    # One clone per application repo, shared by an application listed under
    # more than one group.
    repos = {app_repo(app) for apps in applications.values() for app in apps}
    checkouts = {repo: clone(repo, args.offline) for repo in sorted(repos)}
    if not args.offline:
        check_repositories(applications, checkouts)

    clean_generated()

    used = set()
    total = 0
    for weight, (group, apps) in enumerate(applications.items(), start=1):
        count = write_group(group, apps, weight * 10, checkouts, used, args.offline)
        print(f">> {group}: {count} pages")
        total += count

    removed = clean_images(used)
    print(f">> {len(used)} images in {IMAGES.relative_to(HERE)}"
          + (f", {removed} stale removed" if removed else ""))

    STATIC.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(
        json.dumps(
            {"generated": generated, "starters": starters,
             "applications": applications},
            indent=2, ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )
    print(f">> wrote {INDEX.relative_to(HERE)}")

    print(f">> generated {total} pages in {len(applications)} groups")

    # "generated" changes on every run, so compare the content itself to decide
    # whether anything worth publishing actually moved.
    if catalog_content(previous) == (starters, applications):
        print(">> starter and application lists unchanged")
    else:
        print(">> starter or application lists changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
