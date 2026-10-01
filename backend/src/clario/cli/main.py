"""`clario` CLI.

  clario serve [--host H] [--port P] [--reload | --no-reload]   reloads by default in development
  clario db upgrade [REVISION]        apply migrations (default: head); idempotent
  clario db current                   show the applied revision
  clario db revision -m MSG [--autogenerate]
  clario openapi export [--check]     write contracts/openapi.json (or fail if it is out of date)
  clario admin …                      provision users/workspaces (see `clario admin --help`)
  clario dev seed --owner-email E     development user + workspace (APP_ENV=development only)

Destructive database commands (downgrade, reset) are deliberately not offered.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from clario.cli import admin, dev
from clario.cli import sync as sync_cli
from clario.settings import REPO_ROOT, get_settings

BACKEND_ROOT = REPO_ROOT / "backend"
OPENAPI_PATH = REPO_ROOT / "contracts" / "openapi.json"


def alembic_config(database_url: str | None = None) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    # Migrations use the direct endpoint (never the PgBouncer pool). `%` is configparser syntax.
    url = database_url or get_settings().migration_database_url
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def _serve(args: argparse.Namespace) -> int:
    import uvicorn

    from clario.settings import AppEnv

    # In development a server that outlives code changes serves stale routes (an old process
    # answered the chat routes with 404), so reloading is the default there.
    reload = (
        args.reload if args.reload is not None else get_settings().app_env is AppEnv.DEVELOPMENT
    )
    uvicorn.run(
        "clario.main:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=reload,
        reload_dirs=[str(BACKEND_ROOT / "src")] if reload else None,
        log_config=None,  # clario.core.logs configures logging
        proxy_headers=True,
    )
    return 0


def _db_upgrade(args: argparse.Namespace) -> int:
    command.upgrade(alembic_config(), args.revision)
    return 0


def _db_current(_: argparse.Namespace) -> int:
    command.current(alembic_config(), verbose=True)
    return 0


def _db_revision(args: argparse.Namespace) -> int:
    command.revision(alembic_config(), message=args.message, autogenerate=args.autogenerate)
    return 0


def render_openapi() -> str:
    from clario.main import create_app

    schema = create_app().openapi()
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _openapi_export(args: argparse.Namespace) -> int:
    rendered = render_openapi()
    path = Path(args.output)
    if args.check:
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        if current != rendered:
            print(f"{path} is out of date. Run: clario openapi export", file=sys.stderr)
            return 1
        print(f"{path} is up to date.")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"Wrote {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clario", description="Clario backend command-line tools")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Run the API server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument(
        "--reload",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Reload on code changes (default: on when APP_ENV=development)",
    )
    serve.set_defaults(func=_serve)

    db = sub.add_parser("db", help="Database migrations").add_subparsers(
        dest="db_command", required=True
    )
    upgrade = db.add_parser("upgrade", help="Apply migrations (idempotent)")
    upgrade.add_argument("revision", nargs="?", default="head")
    upgrade.set_defaults(func=_db_upgrade)
    db.add_parser("current", help="Show the applied revision").set_defaults(func=_db_current)
    revision = db.add_parser("revision", help="Create a new migration")
    revision.add_argument("-m", "--message", required=True)
    revision.add_argument("--autogenerate", action="store_true")
    revision.set_defaults(func=_db_revision)

    openapi = sub.add_parser("openapi", help="OpenAPI contract").add_subparsers(
        dest="openapi_command", required=True
    )
    export = openapi.add_parser("export", help="Write contracts/openapi.json")
    export.add_argument("--output", default=str(OPENAPI_PATH))
    export.add_argument(
        "--check", action="store_true", help="Fail if the committed file is out of date"
    )
    export.set_defaults(func=_openapi_export)
    admin.register(sub)
    dev.register(sub)
    sync_cli.register(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
