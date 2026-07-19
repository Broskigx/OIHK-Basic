#!/usr/bin/env python3
"""OIHK Basic — Local-first investigation platform.

Usage:
    python run.py              # Start with defaults
    python run.py --port 8080  # Custom port
    python run.py --help       # Full options
"""

import argparse
import sys
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
    args = parser.parse_args()

    print(f"Starting OIHK Basic on http://{args.host}:{args.port}")
    print("API docs at http://{args.host}:{args.port}/docs")

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
