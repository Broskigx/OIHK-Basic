"""The E2E smoke has to relaunch itself without losing its exit status.

The smoke needs both products importable, so it re-runs itself under the venv
that installed them. It did that with ``os.execv``, which is correct on POSIX
and wrong on Windows: the CRT implements exec by spawning a new process and
terminating the current one, so the caller's wait returns immediately with 0
while the build is still running. A CI job would read that as "18 steps
passed" before a single step had started — the worst answer a smoke test can
give, because it is green.

The relaunch also has to forward every flag the parser accepts, which it did
not: ``--port`` was dropped, so the documented flag silently ran the backend
on a random free port instead.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "smoke_system_link_e2e.py"


def _load_smoke():
    """Import the smoke script as a module (stdlib-only at import time)."""
    spec = importlib.util.spec_from_file_location("smoke_system_link_e2e", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _args(**overrides) -> argparse.Namespace:
    return SimpleNamespace(**{"port": 0, "keep": False, **overrides})


def test_the_relaunch_forwards_the_port_it_was_given() -> None:
    smoke = _load_smoke()
    argv = smoke._relaunch_argv(SCRIPT, Path("/venv/python"), Path("/lab"), _args(port=8123))
    assert "--port" in argv, "--port never reached the smoke venv, so the flag did nothing"
    assert argv[argv.index("--port") + 1] == "8123"


def test_a_default_port_is_not_forwarded_as_zero() -> None:
    """Port 0 means "pick a free one", and the child picks it itself."""
    smoke = _load_smoke()
    assert "--port" not in smoke._relaunch_argv(SCRIPT, Path("/venv/python"), Path("/lab"), _args())


@pytest.mark.parametrize("keep", [True, False])
def test_keep_is_forwarded_only_when_asked(keep: bool) -> None:
    smoke = _load_smoke()
    argv = smoke._relaunch_argv(SCRIPT, Path("/venv/python"), Path("/lab"), _args(keep=keep))
    assert ("--keep" in argv) is keep


def test_the_relaunch_runs_the_smoke_venv_interpreter_on_this_script() -> None:
    smoke = _load_smoke()
    argv = smoke._relaunch_argv(SCRIPT, Path("/venv/python"), Path("/lab"), _args())
    assert argv[0] == str(Path("/venv/python"))
    assert argv[1] == str(SCRIPT)
    assert argv[argv.index("--evidence-lab") + 1] == str(Path("/lab"))


@pytest.mark.parametrize("code", [0, 1, 7])
def test_the_childs_exit_status_becomes_the_scripts_exit_status(monkeypatch: pytest.MonkeyPatch, code: int) -> None:
    """A failed smoke must not report success to whatever ran it."""
    smoke = _load_smoke()
    seen: dict[str, object] = {}

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        return subprocess.CompletedProcess(argv, code)

    monkeypatch.setattr(smoke.subprocess, "run", fake_run)
    assert smoke._relaunch_in_smoke_venv(SCRIPT, Path("/venv/python"), Path("/lab"), _args()) == code
    assert seen["argv"][0] == str(Path("/venv/python"))


def test_the_relaunch_does_not_hand_the_process_over_to_exec() -> None:
    """Guards the platform trap this module exists to describe.

    ``os.execv`` leaves no trace when it misbehaves: the process is gone, the
    caller sees 0, and the smoke keeps running orphaned. Nothing downstream can
    detect that, so the check lives at the source level.

    Read as an AST rather than searched as text, so the comment in the script
    that warns about this trap does not itself trip the guard — a check that
    forbids naming the hazard would push the explanation out of the code.
    """
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    called = {
        f"{node.func.value.id}.{node.func.attr}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
    }
    forbidden = {name for name in called if name.startswith("os.exec")}
    assert not forbidden, (
        f"{sorted(forbidden)} terminates this process on Windows and returns 0 to the caller "
        "while the smoke is still running; run the child and propagate its status instead"
    )


def test_the_script_still_parses_and_exposes_its_documented_flags() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for flag in ("--evidence-lab", "--port", "--keep"):
        assert flag in result.stdout
