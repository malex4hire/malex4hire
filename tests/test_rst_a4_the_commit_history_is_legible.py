"""RST-A4: the work reads as work, one commit per constraint it satisfies.

A squashed branch is a diff with no argument in it. Somebody arriving here in six months
reads the history to find out why the page is generated rather than written, and a single
commit called "profile" answers nothing.

The set is derived, not typed: it is the RST identifiers this repository's own test files
carry. A constraint that arrives with a check and no commit naming it fails here, and so
does a branch collapsed into one commit claiming all of them.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEST_FILE = re.compile(r"^test_(rst_[a-z]\d+)_")
SEPARATOR = "\x1f"


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=60,
    )


def _owed() -> set[str]:
    """The RST identifiers this repository carries a check for.

    A file the glob finds and the pattern rejects is a FAILURE, not a skip. `test_rst_a6.py`
    - no trailing description - was found by the glob, rejected by the pattern, and dropped
    with no warning, so the check whose job is "a constraint with no commit behind it fails"
    never asked about it. A set built by discarding what it cannot parse is a set that
    quietly shrinks to nothing.
    """
    found, unparsed = set(), []
    for path in sorted((ROOT / "tests").glob("test_rst_*.py")):
        match = TEST_FILE.match(path.name)
        if match:
            found.add(match.group(1).replace("_", "-").upper())
        else:
            unparsed.append(path.name)
    if unparsed:
        pytest.fail(
            "these files name an RST constraint in a shape this check cannot read, so they "
            "would be dropped from the set silently: " + ", ".join(unparsed)
            + "\n\nExpected test_rst_<letter><digits>_<description>.py"
        )
    return found


def _history() -> list[tuple[str, str]]:
    """Every commit reachable from HEAD, as (sha, subject).

    A shallow clone fails with a named reason rather than skipping. The history is the
    input to this check, and a check that quietly passes when its input is missing is
    exactly the shape this whole repository is built against.
    """
    if not (ROOT / ".git").exists():
        pytest.fail("MISSING INPUT: no .git directory, so there is no history to read")

    shallow = _git("rev-parse", "--is-shallow-repository")
    if shallow.returncode == 0 and shallow.stdout.strip() == "true":
        pytest.fail(
            "MISSING INPUT: this is a shallow clone, so the history this check reads is "
            "not present. CI needs `fetch-depth: 0` on actions/checkout"
        )

    log = _git("log", f"--format=%H{SEPARATOR}%s")
    if log.returncode != 0:
        pytest.fail(f"UNREADABLE INPUT: git log failed: {log.stderr.strip()}")

    commits = []
    for line in log.stdout.splitlines():
        sha, _, subject = line.partition(SEPARATOR)
        if sha:
            commits.append((sha, subject))
    assert commits, "git log returned no commits"
    return commits

# A bare substring is not an identifier match: "RST-A1" is a prefix of "RST-A10", so a
# single RST-A10 commit would report RST-A1 as having a commit behind it. Latent while
# there are fewer than ten constraints, and wrong the moment there are not.
def _names(identifier: str, subject: str) -> bool:
    return bool(re.search(rf"(?<![\w-]){re.escape(identifier)}(?![\w-])", subject, re.I))


def _naming() -> dict[str, list[tuple[str, str]]]:
    """For each constraint, the commits whose subject names it."""
    commits = _history()
    return {
        identifier: [(sha, subject) for sha, subject in commits if _names(identifier, subject)]
        for identifier in sorted(_owed())
    }


def _sole(identifier: str, subject: str, owed: set[str]) -> bool:
    """True when this subject names this constraint and no other.

    The spec is "each commit naming the RST identifier it satisfies", singular. A banner
    subject naming every constraint at once satisfies none of them: it is the squash this
    forbids, and counting it was the hole a review found here. Three banner commits passed
    a cardinality test on the union while no constraint had a commit of its own.
    """
    return _names(identifier, subject) and not any(
        other != identifier and _names(other, subject) for other in owed
    )


def test_every_constraint_with_a_check_has_a_commit_that_names_it():
    owed = _owed()
    assert owed, (
        "no tests/test_rst_*.py files, so nothing here claims to satisfy a constraint and "
        "this check has no set to work from"
    )
    naming = _naming()
    unnamed = sorted(i for i, commits in naming.items() if not commits)
    assert not unnamed, (
        "these constraints have a check in tests/ and no commit subject naming them: "
        + ", ".join(unnamed)
        + ". A check with no commit behind it is work whose reason lives nowhere"
    )


def test_every_constraint_has_a_commit_of_its_own():
    """One commit per constraint, and a banner naming all of them is not one of them.

    This is the assertion that forbids a squash. Counting commits that mention any
    identifier does not: a review showed three subjects each naming all three constraints
    clearing a cardinality test while no constraint had a commit to itself.
    """
    owed = _owed()
    naming = _naming()
    shared = {
        identifier: [sha for sha, subject in commits if _sole(identifier, subject, owed)]
        for identifier, commits in naming.items()
    }
    without = sorted(i for i, shas in shared.items() if not shas)
    assert not without, (
        "these constraints are named only by commits that also name another, so none of "
        "them landed as its own commit: " + ", ".join(without)
        + "\n\n"
        + "\n".join(
            f"  {i}: " + (", ".join(s[:8] for s in shas[:3]) or "no commit of its own")
            for i, shas in sorted(shared.items())
        )
    )
