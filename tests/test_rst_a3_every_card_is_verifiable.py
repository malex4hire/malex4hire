"""RST-A3: every card on this page resolves against the repository it points at.

A profile page is the first URL a reviewer opens, and it is the one page nothing checks.
It is prose about other people's work - or in this case, about repositories that change
after the prose is written - and the failure mode is silent: a card goes on describing a
command that was renamed, a gate that was renumbered, an artifact that moved.

So the page is generated from profile.yaml, and every claim on it is a binding with a path
in its target repository. These checks resolve all of them against the live repositories.
A card that outruns what its repository actually contains fails here.

Six things are checked:

1. The positioning is three lines or fewer.
2. README.md reproduces from profile.yaml, so a hand edit cannot introduce a claim that
   skipped the bindings.
3. There is one card per public repository, read from the account rather than from a list
   kept here. A repository going public with no card is a gap this finds.
4. Every outbound link resolves.
5. Every binding's path exists in its target repository, and the value the card prints is
   present in that repository.
6. No card carries a superlative. A superlative is unbound by construction: there is no
   file that proves "best".

The network is an input. Where it is unreachable these fail with a named reason rather
than skipping, because a check that goes quiet when its input is missing is the shape
this whole page is trying not to be.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profile.yaml"
README = ROOT / "README.md"
OWNER = "malex4hire"

# The profile repository holds the page; a card pointing at the page the card is on says
# nothing. Declared here rather than filtered silently, so the exclusion is visible.
NOT_CARDED = {OWNER}

# Words that cannot be bound to a file. Each one is a claim about a comparison nobody ran,
# and the point of this page is that every claim on it names something checkable.
SUPERLATIVES = (
    "best", "world-class", "cutting-edge", "state-of-the-art", "revolutionary",
    "seamless", "blazing", "unmatched", "industry-leading", "bulletproof",
    "ultimate", "flawless", "unparalleled", "game-changing", "next-generation",
    "enterprise-grade", "production-ready", "battle-tested", "rock-solid",
)

USER_AGENT = "malex4hire-profile-checks/1.0 (+https://github.com/malex4hire/malex4hire)"
TIMEOUT = 30


# ---------------------------------------------------------------------------
# readers
# ---------------------------------------------------------------------------

def _bounded(value: str) -> re.Pattern:
    """A binding's value, matched on its own rather than as a substring.

    `R-8` is inside `R-80`, so renumbering a gate in the target repository would leave the
    card resolving forever while printing an identifier that no longer exists. One
    definition, shared by the check and by the test that proves it fires - the first
    version of this lived inline in the check and nothing exercised it.
    """
    return re.compile(rf"(?<![\w-]){re.escape(value)}(?![\w-])")


def profile() -> dict:
    if not PROFILE.is_file():
        pytest.fail(f"MISSING INPUT: {PROFILE.name} not found; it is the page's source")
    doc = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        pytest.fail(f"MALFORMED INPUT: {PROFILE.name} must be a mapping")
    for key in ("positioning", "cards"):
        if key not in doc:
            pytest.fail(f"MALFORMED INPUT: {PROFILE.name} declares no '{key}'")
    return doc


def renderer():
    sys.path.insert(0, str(ROOT / "scripts"))
    import importlib

    if not (ROOT / "scripts" / "render_readme.py").is_file():
        pytest.fail("MISSING INPUT: scripts/render_readme.py, which produces the page")
    return importlib.import_module("render_readme")


def _fetch(url: str, accept: str = "application/vnd.github+json"):
    """One request, with a named failure rather than a skip when the network is absent."""
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": accept,
    })
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token and "api.github.com" in url:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, b""
    except urllib.error.URLError as exc:
        pytest.fail(
            f"UNREACHABLE INPUT: {url} could not be reached ({exc.reason}). These checks "
            "resolve claims against live repositories, so an unreachable network is a "
            "check that did not run, not a check that passed"
        )


def public_repositories() -> set[str]:
    status, body = _fetch(f"https://api.github.com/users/{OWNER}/repos?per_page=100&type=owner")
    if status == 403:
        pytest.fail(
            "the GitHub API refused the repository listing (rate limited). Set GITHUB_TOKEN "
            "so this check can read the set it is asserting against"
        )
    assert status == 200, f"listing {OWNER}'s repositories returned {status}"
    return {
        repo["name"] for repo in json.loads(body)
        if not repo.get("private") and not repo.get("archived")
    }


def _raw(repo: str, path: str) -> tuple[int, str]:
    status, body = _fetch(
        f"https://raw.githubusercontent.com/{OWNER}/{repo}/main/{path}", accept="text/plain"
    )
    return status, body.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------

def test_the_positioning_is_three_lines_or_fewer():
    lines = [str(line).strip() for line in profile()["positioning"] if str(line).strip()]
    assert lines, "the page has no positioning at all"
    assert len(lines) <= 3, (
        f"the positioning is {len(lines)} lines. Three is the ceiling: a reader who needs "
        "four lines of preamble has already left"
    )


def test_the_page_reproduces_from_its_source():
    """A hand edit is how a claim gets onto the page without passing the bindings."""
    if not README.is_file():
        pytest.fail("MISSING INPUT: README.md has not been rendered")
    fresh = renderer().render()
    assert README.read_text(encoding="utf-8") == fresh, (
        "README.md differs from what profile.yaml renders. Edit profile.yaml and run "
        "`python3 scripts/render_readme.py`; a page edited by hand carries claims nothing "
        "resolved"
    )


def test_there_is_one_card_per_public_repository():
    carded = set(profile()["cards"])
    public = public_repositories() - NOT_CARDED

    missing = sorted(public - carded)
    stale = sorted(carded - public)

    assert not missing, (
        "public repositories with no card: " + ", ".join(missing)
        + ". The set is read from the account, so a repository going public is a gap this "
        "finds rather than one somebody has to remember"
    )
    assert not stale, (
        "cards for repositories that are not public: " + ", ".join(stale)
        + ". A link a reviewer cannot open is worse than no card"
    )


def test_every_outbound_link_resolves():
    if not README.is_file():
        pytest.fail("MISSING INPUT: README.md has not been rendered")
    links = sorted(set(re.findall(r"\]\((https?://[^)\s]+)\)", README.read_text(encoding="utf-8"))))
    assert links, "the page has no outbound links, so it points at nothing"

    broken = []
    for url in links:
        status, _ = _fetch(url, accept="text/html,application/xhtml+xml")
        if status != 200:
            broken.append(f"{url} -> {status}")
    assert not broken, "the page links to things that do not resolve:\n  " + "\n  ".join(broken)


def test_every_binding_exists_in_the_repository_the_card_points_at():
    """The check that makes a card a claim rather than a sentence.

    Both halves matter. The path is what makes the binding addressable; the value is what
    the card actually prints, and a path that exists while the card names a command that
    was renamed is the failure this is for.
    """
    problems = []
    for name, card in profile()["cards"].items():
        bindings = card.get("bindings") or []
        if not bindings:
            problems.append(f"{name}: no binding, so the card states something and proves nothing")
            continue

        for binding in bindings:
            path, value = binding["path"], str(binding["value"])
            status, body = _raw(name, path)
            if status != 200:
                problems.append(f"{name}: {path} does not exist on main ({status})")
                continue

            # Where the value must be found, declared per binding and defaulting to the
            # path itself. A blanket fallback to the target repository's README dissolves
            # the rename this check exists to catch: a gate renamed in the test file, with
            # the old name still sitting in a changelog line, would resolve forever. READMEs
            # lag renames - that is the premise of this whole page.
            states = binding.get("states", path)
            if states == path:
                haystack, where = body, path
            else:
                status, haystack = _raw(name, states)
                where = states
                if status != 200:
                    problems.append(f"{name}: {states} does not exist on main ({status})")
                    continue

            # A bounded match, not a bare substring. `R-8` is inside `R-80`, so renumbering
            # a gate in the target repository would leave the card resolving forever while
            # printing an identifier that no longer exists - the exact failure this check
            # is for. The sibling commit-history check was given this boundary an hour
            # earlier and this one was not, which is the same defect class twice in two
            # files.
            if not _bounded(value).search(haystack) and value != path:
                problems.append(
                    f"{name}: the card prints `{value}` and {where} does not contain it"
                )

    assert not problems, (
        "cards making claims their repositories do not support:\n  " + "\n  ".join(problems)
    )


def test_no_card_carries_a_superlative():
    doc = profile()
    text = yaml.safe_dump(
        {"positioning": doc["positioning"], "cards": doc["cards"],
         "preamble": doc.get("preamble", ""), "footer": doc.get("footer", "")}
    ).lower()

    found = sorted({word for word in SUPERLATIVES if word in text})
    assert not found, (
        "the page carries superlatives, and a superlative has no file behind it: "
        + ", ".join(found)
        + ". Say what the repository does and name what proves it"
    )


def test_adding_a_card_leaves_the_positioning_and_the_layout_untouched():
    """The forward requirement, checked rather than asserted in a comment.

    One repository here is unpublished and will need a card. If adding it means re-laying
    out the page, the page will be re-laid out by hand under time pressure and the cards
    will drift from what the bindings say. So this renders the page with an extra card and
    requires that everything except the cards region came through unchanged.
    """
    render = renderer()
    doc = profile()
    before = render.render()

    extra = dict(doc["cards"])
    first = next(iter(doc["cards"].values()))
    extra["a-repository-that-does-not-exist-yet"] = {
        "line": first.get("line", "placeholder"),
        "proves": "placeholder",
        "bindings": [{"kind": "artifact", "value": "README.md", "path": "README.md"}],
    }

    original = render.profile
    render.profile = lambda: {**doc, "cards": extra}
    try:
        after = render.render()
    finally:
        render.profile = original

    def outside_cards(page: str) -> tuple[str, str]:
        """Everything before and after the cards, sliced on the renderer's own markers.

        Locating the region by its first and last `---` looked equivalent and was not: the
        trailing separator only exists when profile.yaml declares a footer, so with no
        footer the slice silently became the whole page and this test compared the cards to
        themselves. It then failed, saying the layout had changed when nothing outside the
        cards had, which sends the next reader to the wrong file.
        """
        assert render.CARDS_OPEN in page and render.CARDS_CLOSE in page, (
            "the rendered page carries no cards markers, so the region cannot be located"
        )
        head, _, rest = page.partition(render.CARDS_OPEN)
        _, _, tail = rest.partition(render.CARDS_CLOSE)
        return head, tail

    assert outside_cards(before) == outside_cards(after), (
        "adding a card changed the page outside the cards region. Adding a repository has "
        "to be adding a row; a layout that must be re-laid out every time the estate grows "
        "is a layout that stops being maintained"
    )
    assert after != before, "the extra card did not render at all, so this proved nothing"


# ---------------------------------------------------------------------------
# The controls this file's own fixes added. Landed here because they were landed
# in DECISIONS.md instead, which is not a place a check can fire from: a review
# mutated both and the suite stayed green, so both were decoration.
# ---------------------------------------------------------------------------

def test_render_refuses_an_argument_it_does_not_recognise():
    """A misspelt flag must not fall through to the write path.

    `--checkk` once re-rendered the page, discarded a hand edit and exited 0, so the CI
    step was one character from the bug that flag exists to prevent. The assertion that
    matters is the second one: the edit SURVIVES. An exit code alone would pass for a
    version that refused the flag and wrote the file anyway.
    """
    render = renderer()
    if not README.is_file():
        pytest.fail("MISSING INPUT: README.md has not been rendered")

    before = README.read_text(encoding="utf-8")
    marker = "\n<!-- a hand edit that skipped the bindings -->\n"
    README.write_text(before + marker, encoding="utf-8")
    try:
        for argument in ("--checkk", "-c", "--help", "--check-drift"):
            code = render.main([argument])
            assert code == 2, (
                f"`{argument}` returned {code}; anything but --check must be refused, or a "
                "typo in the workflow silently restores the write path"
            )
            assert marker in README.read_text(encoding="utf-8"), (
                f"`{argument}` rewrote README.md. A refused argument must not write: that "
                "is the whole reason --check exists"
            )
        assert render.main(["--check"]) == 1, "--check must fail on a drifted page"
    finally:
        README.write_text(before, encoding="utf-8")

    assert render.main(["--check"]) == 0, "--check must pass on the committed page"


def test_the_workflow_verifies_the_page_and_does_not_rewrite_it():
    """The invariant is "this process must not write in CI", not the flag's spelling.

    Refusing `--checkk` does nothing about `--check` being DELETED from the recipe, which
    is the same one-token edit and puts the page back to being rendered on the runner
    before the test asserts it reproduces. So the recipe itself is read.
    """
    workflow = ROOT / ".github" / "workflows" / "cards.yml"
    if not workflow.is_file():
        pytest.fail(f"MISSING INPUT: {workflow.name}, which is what runs these checks")

    invocations = [
        line.strip() for line in workflow.read_text(encoding="utf-8").splitlines()
        if "render_readme.py" in line
    ]
    assert invocations, (
        "the workflow never invokes the renderer, so nothing there verifies the page"
    )
    writing = [line for line in invocations if "--check" not in line]
    assert not writing, (
        "the workflow invokes the renderer without --check, so it rewrites README.md on "
        "the runner before the reproduction test looks at it:\n  " + "\n  ".join(writing)
    )


def test_a_binding_value_is_matched_with_a_boundary():
    """`R-8` must not resolve against a haystack that only contains `R-80`.

    The boundary was applied to the sibling commit-history check and not to this one, and
    then landed here with no test, so reverting it to a bare substring left the suite green.
    """
    bounded = _bounded("R-8")
    assert not bounded.search('"""R-80: the demo runs on a bare interpreter.'), (
        "a renumbered gate still resolves; the card would print an identifier that no "
        "longer exists"
    )
    assert bounded.search('"""R-8: the demo runs on a bare interpreter.'), (
        "the boundary rejects the identifier it is supposed to match"
    )
    assert _bounded("make demo").search("\tmake demo\n"), (
        "a value surrounded by whitespace must still match"
    )
