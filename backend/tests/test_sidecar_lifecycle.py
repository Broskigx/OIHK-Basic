from __future__ import annotations

import os
from types import SimpleNamespace

import run as backend_run


def test_parent_liveness_detects_current_process() -> None:
    assert backend_run._parent_is_alive(os.getpid()) is True


def test_parent_watchdog_requests_shutdown_when_parent_exits(monkeypatch) -> None:
    server = SimpleNamespace(should_exit=False)
    monkeypatch.setattr(backend_run, "_parent_is_alive", lambda _pid: False)
    backend_run._watch_parent(server, 999_999, poll_interval=0)
    assert server.should_exit is True
