"""Command-line entry points for local development."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import subprocess
import sys
import time

from clario.config import get_settings
from clario.logging import configure_logging


def _pids_on_port(port: int) -> list[int]:
    try:
        out = subprocess.check_output(
            ["lsof", "-ti", f"TCP:{port}", "-sTCP:LISTEN"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    pids: list[int] = []
    for line in out.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return pids


def _stop_port(port: int) -> list[int]:
    pids = _pids_on_port(port)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
    deadline = time.time() + 5
    while time.time() < deadline and _pids_on_port(port):
        time.sleep(0.15)
    for pid in _pids_on_port(port):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            continue
    return pids


def _run_serve(settings) -> int:
    import uvicorn

    uvicorn.run(
        "clario.api.main:app",
        host=settings.clario_host,
        port=settings.clario_port,
        reload=False,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="clario", description="Clario MVP commands")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("serve", help="Start the FastAPI app (OAuth + chat UI)")
    sub.add_parser(
        "restart",
        help="Stop anything on CLARIO_PORT, then start the app (reloads .env)",
    )
    sub.add_parser("oauth-url", help="Print the Zoho authorization URL")
    sub.add_parser("smoke", help="Run live Zoho integration checks")
    eval_parser = sub.add_parser("eval", help="Ask the Clario agent a question")
    eval_parser.add_argument("question", nargs="+")

    args = parser.parse_args(argv)
    settings = get_settings()
    configure_logging(settings.clario_log_level)

    if args.command == "serve":
        return _run_serve(settings)
    if args.command == "restart":
        stopped = _stop_port(settings.clario_port)
        if stopped:
            print(
                f"Stopped PID(s) on :{settings.clario_port}: {', '.join(map(str, stopped))}",
                file=sys.stderr,
            )
        else:
            print(f"Nothing listening on :{settings.clario_port}", file=sys.stderr)
        print(
            f"Starting Clario at http://{settings.clario_host}:{settings.clario_port}",
            file=sys.stderr,
        )
        return _run_serve(settings)
    if args.command == "oauth-url":
        from clario.zoho.oauth import ZohoOAuth

        url, state = ZohoOAuth(settings).authorization_url()
        print(url)
        print(f"# state={state}", file=sys.stderr)
        return 0
    if args.command == "smoke":
        from clario.scripts_api import run_smoke

        return asyncio.run(run_smoke())
    if args.command == "eval":
        from clario.agent.runner import get_runner

        question = " ".join(args.question)
        result = asyncio.run(get_runner().ask(question))
        print(json.dumps({"tool_calls": result["tool_calls"]}, indent=2))
        print()
        print(result["answer"])
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
