#!/usr/bin/env python3
"""OIHK Basic — Local-first investigation platform.

Usage:
    python run.py              # Start with defaults
    python run.py --port 8080  # Custom port
    python run.py --help       # Full options
"""

import argparse
import os
import sys
import threading
import time
from contextlib import suppress
from pathlib import Path

# PyInstaller's windowed bootloader does not attach console streams on Windows.
# Uvicorn and the startup banner still expect writable streams, so route them to
# the platform null device before importing Uvicorn when no console is present.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115

import uvicorn


def _parent_is_alive(parent_pid: int) -> bool:
    if parent_pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        synchronize = 0x00100000
        wait_timeout = 0x00000102
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel32.OpenProcess(synchronize, False, parent_pid)
        if not handle:
            return False
        try:
            return kernel32.WaitForSingleObject(handle, 0) == wait_timeout
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(parent_pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


def _watch_parent(server, parent_pid: int, poll_interval: float = 1.0) -> None:
    while not server.should_exit:
        if not _parent_is_alive(parent_pid):
            server.should_exit = True
            return
        time.sleep(poll_interval)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="OIHK Basic — Local-first investigation and OSINT platform",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind address (default: 127.0.0.1, use 0.0.0.0 with caution)",
    )
    parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    parser.add_argument("--parent-pid", type=int, default=0, help=argparse.SUPPRESS)
    parser.add_argument("--data-dir", default="", help=argparse.SUPPRESS)
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error"])

    # Support --port via environment variable (used by Tauri sidecar launch)
    env_port = os.environ.get("OIHK_PORT")
    if env_port:
        with suppress(ValueError):
            parser.set_defaults(port=int(env_port))

    args = parser.parse_args()
    os.environ.pop("OIHK_PACKAGED_DATA_DIR", None)
    # Make the app startup hardening check aware of the real bind address.
    os.environ["OIHK_SERVER_BIND_HOST"] = args.host
    if args.data_dir:
        requested_data_dir = Path(args.data_dir)
        if not requested_data_dir.is_absolute():
            parser.error("The managed data directory must be absolute.")
        data_dir = requested_data_dir.resolve()
        os.environ["OIHK_PACKAGED_DATA_DIR"] = str(data_dir)

    # Importing the configuration is what loads — or creates — this
    # installation's keys, so it is also where the deliberate refusal to rotate
    # them surfaces. Left uncaught it reaches the operator as a traceback, and
    # through the desktop shell as nothing but "the backend exited": a
    # carefully worded fail-closed message delivered as a generic crash. Catch
    # it here and say what happened and what to do about it.
    from app.core.first_run import SecretsFileError

    try:
        from app.core.config import get_settings
    except SecretsFileError as exc:
        print(f"OIHK Basic cannot start: {exc}", file=sys.stderr)
        print(
            "The keys that seal this installation's custody records are stored "
            "separately from its database. Restore the secrets file from a "
            "backup to keep the existing evidence verifiable, or move the "
            "database aside to start a new profile with new keys.",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc

    if not get_settings().auth_enabled and args.host not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("Authentication is disabled; OIHK Basic may only bind to a loopback address.")

    print(f"Starting OIHK Basic on http://{args.host}:{args.port}")
    print(f"API docs at http://{args.host}:{args.port}/docs")

    # Import app directly so PyInstaller bundles resolve correctly
    from app.main import app

    if args.reload:
        uvicorn.run(
            "app.main:app",
            host=args.host,
            port=args.port,
            reload=True,
            log_level=args.log_level,
        )
        return

    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=args.host,
            port=args.port,
            log_level=args.log_level,
        )
    )
    app.state.shutdown_callback = lambda: setattr(server, "should_exit", True)
    if args.parent_pid:
        threading.Thread(
            target=_watch_parent,
            args=(server, args.parent_pid),
            name="oihk-parent-watchdog",
            daemon=True,
        ).start()
    server.run()


if __name__ == "__main__":
    main()
