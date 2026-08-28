"""The release build must run the tests the way CI runs them.

pytest derives its rootdir from the arguments it is given. With `backend/tests`
among them it finds `backend/pyproject.toml` and applies `asyncio_mode =
"auto"`; invoked bare from the project root it finds no config at all, falls
back to strict mode, and every sync test that depends on an async fixture
errors at setup.

That is not hypothetical. CI ran `pytest backend/tests tests` and was green
while the Windows release build ran a bare `pytest` and died with 132 setup
errors — so a green CI said nothing about whether a release would build, which
is the one thing a release gate is for.

These tests pin the two invocations together. They read both files rather than
running anything, because the failure is in the argument list, not in the code
under test.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts" / "build-windows.ps1"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

# The suites both commands must cover. Named here so adding a third one is a
# deliberate edit in one place rather than a silent divergence in two.
REQUIRED_SUITES = ("backend", "tests")


def _ci_pytest_command() -> str:
    """The CI pytest line, read textually rather than through a YAML parser.

    PyYAML is in the lockfile but is not a declared dependency of this project,
    so importing it here would make the test pass on the Windows job (which
    installs the lock) and error on the Linux one (which installs the declared
    extras). A test that depends on an undeclared package is a test that
    reports on the environment rather than on the code.
    """
    lines = CI_WORKFLOW.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if "-m pytest" not in line:
            continue
        # The step uses a folded scalar, so the arguments continue on the
        # following indented lines until the next key or blank line.
        collected = [line.strip()]
        for continuation in lines[index + 1 :]:
            if not continuation.strip() or re.match(r"\s*[-\w]+:", continuation):
                break
            collected.append(continuation.strip())
        return " ".join(collected)
    pytest.fail("no pytest invocation found in the CI workflow")


def _build_pytest_command() -> str:
    """The build's pytest line with its PowerShell path variables resolved.

    Comparing the two commands as raw text would compare PowerShell against
    bash and fail on the syntax rather than on the paths. Substituting the
    variables first means the assertion is about which suites run, which is the
    thing that actually has to match.
    """
    substitutions = {"$BackendDir": "backend", "$ProjectRoot": "."}
    for line in BUILD_SCRIPT.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "-m pytest" in stripped:
            for variable, path in substitutions.items():
                stripped = stripped.replace(variable, path)
            return stripped
    pytest.fail("no pytest invocation found in build-windows.ps1")


def test_the_release_build_names_its_test_paths() -> None:
    """A bare `pytest` from the project root picks up no configuration at all."""
    command = _build_pytest_command()
    assert "tests" in command, (
        "build-windows.ps1 runs pytest without naming a test path; from the project "
        "root that resolves rootdir to a directory with no pytest config, so "
        'asyncio_mode falls back to strict and async fixtures stop working'
    )


@pytest.mark.parametrize("suite", REQUIRED_SUITES)
def test_both_commands_cover_the_same_suites(suite: str) -> None:
    build = _build_pytest_command()
    ci = _ci_pytest_command()
    assert suite in build, f"the release build does not run the {suite} suite"
    assert suite in ci, f"CI does not run the {suite} suite"


def test_the_release_build_reaches_the_backend_pytest_configuration() -> None:
    """`backend/pyproject.toml` holds asyncio_mode, and only an argument under
    `backend/` makes pytest discover it."""
    assert "backend" in _build_pytest_command(), (
        "no argument under backend/ means pytest never reads backend/pyproject.toml"
    )


def test_the_backend_configuration_still_declares_auto_asyncio_mode() -> None:
    """If this moves, the argument-order reasoning above stops applying."""
    config = (ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'asyncio_mode\s*=\s*"auto"', config), (
        "asyncio_mode is no longer declared in backend/pyproject.toml; the release "
        "build and CI both rely on pytest discovering it from there"
    )
