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
    found = set()
    for path in sorted((ROOT / "tests").glob("test_rst_*.py")):
        match = TEST_FILE.match(path.name)
        if match:
            found.add(match.group(1).replace("_", "-").upper())
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


def _naming() -> dict[str, set[str]]:
    commits = _history()
    return {
        identifier: {sha for sha, subject in commits if identifier.lower() in subject.lower()}
        for identifier in sorted(_owed())
    }


def test_every_constraint_with_a_check_has_a_commit_that_names_it():
    owed = _owed()
    assert owed, "no tests/test_rst_*.py files, so this check has no set to work from"

    naming = _naming()
    unnamed = sorted(i for i, shas in naming.items() if not shas)
    assert not unnamed, (
        "these constraints have a check in tests/ and no commit subject naming them: "
        + ", ".join(unnamed)
        + ". A check with no commit behind it is work whose reason lives nowhere"
    )


def test_the_constraints_did_not_all_land_in_one_commit():
    owed, naming = _owed(), _naming()
    distinct = set().union(*naming.values()) if naming else set()
    assert len(distinct) >= len(owed), (
        f"{len(owed)} constraints are claimed by {len(distinct)} commit(s). One commit "
        "answering for all of them is a diff with no argument in it:\n  "
        + "\n  ".join(f"{i}: {sorted(s)[:2] or 'none'}" for i, s in sorted(naming.items()))
    )
