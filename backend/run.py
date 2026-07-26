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
from contextlib import suppress

# PyInstaller's windowed bootloader does not attach console streams on Windows.
# Uvicorn and the startup banner still expect writable streams, so route them to
# the platform null device before importing Uvicorn when no console is present.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115

import uvicorn


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
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error"])

    # Support --port via environment variable (used by Tauri sidecar launch)
    env_port = os.environ.get("OIHK_PORT")
    if env_port:
        with suppress(ValueError):
            parser.set_defaults(port=int(env_port))

    args = parser.parse_args()

    from app.core.config import get_settings

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
    server.run()


if __name__ == "__main__":
    main()
