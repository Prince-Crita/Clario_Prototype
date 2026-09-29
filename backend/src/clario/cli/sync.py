"""`clario sync run` — refresh one workspace's mirror now, inline, and print what landed.

For operators and development (e.g. checking that counts match the source system). The same
engine and rules as the API run it; the run is recorded with the `scheduled` trigger.
"""

from __future__ import annotations

import argparse
import asyncio

from clario.api.registry import build_registry
from clario.cli._support import guarded
from clario.core.db import Database
from clario.platform.connections import service as connections
from clario.platform.sync import repository as sync_repo
from clario.platform.sync.models import SyncTrigger
from clario.platform.sync.service import SyncRunner
from clario.settings import get_settings


def _run(args: argparse.Namespace) -> int:
    async def main() -> int:
        settings = get_settings()
        registry = build_registry()
        database = Database(settings.database_url, pool_size=3, max_overflow=2)
        try:
            async with database.sessions() as session:
                scope = await connections.operator_scope(
                    session, registry, args.workspace, args.integration
                )
            runner = SyncRunner(database, settings, registry)
            outcome = await runner.trigger(scope, SyncTrigger.SCHEDULED)
            if not outcome.started:
                print("A sync is already running for this connection; waiting for it is not")
                print("possible from the CLI. Try again when it has finished.")
                return 1
            await runner.wait_idle()
            async with database.sessions() as session:
                run = await sync_repo.latest_run(session, scope)
                rows = await sync_repo.datasets(session, scope)
            domain = registry.domain(scope.domain)
            print(f"{'dataset':<20} {'status':<8} {'rows':>7}  window")
            for dataset in domain.datasets if domain else ():
                row = rows.get(dataset.key)
                window = (
                    f"{row.window_start} to {row.window_end}" if row and row.window_start else "all"
                )
                error = f"  [{row.last_error_code}]" if row and row.last_error_code else ""
                count = row.row_count if row and row.row_count is not None else 0
                status = row.status if row else "never"
                print(f"{dataset.key:<20} {status:<8} {count:>7}  {window}{error}")
            if run is not None:
                print(
                    f"\nrun {run.status}, {run.api_calls} API calls"
                    + (f", {run.error_code}" if run.error_code else "")
                )
            return 0 if run is not None and run.status == "succeeded" else 1
        finally:
            await database.dispose()

    return asyncio.run(main())


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    sync = subparsers.add_parser("sync", help="Refresh mirrored data (operators)")
    sub = sync.add_subparsers(dest="sync_command", required=True)
    run = sub.add_parser("run", help="Sync one workspace's connection now and print the result")
    run.add_argument("--workspace", required=True, help="Workspace slug")
    run.add_argument("--integration", default="zoho-books")
    run.set_defaults(func=lambda args: guarded(lambda: _run(args)))
