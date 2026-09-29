"""Development helpers, refused outside APP_ENV=development.

* `clario dev seed` — idempotent owner user and workspace.
* `clario dev fixture-connection` — a Zoho Books connection backed by the fixture dataset.
"""

from __future__ import annotations

import argparse

from sqlalchemy.ext.asyncio import AsyncSession

from clario.api.registry import build_registry
from clario.cli._support import guarded, read_password, run_in_session
from clario.core.dates import utc_now
from clario.platform.access.deps import load_workspace_scope
from clario.platform.connections import repository as connection_repo
from clario.platform.connections.models import ConnectionStatus
from clario.platform.identity import repository as identity_repo
from clario.platform.integrations import repository as integration_repo
from clario.platform.integrations import service as integration_service
from clario.platform.integrations.contract import Availability
from clario.platform.workspaces import repository as workspace_repo
from clario.platform.workspaces import service
from clario.settings import AppEnv, get_settings

FIXTURE_ACCOUNT = "fixture"


def _seed(args: argparse.Namespace) -> int:
    if get_settings().app_env is not AppEnv.DEVELOPMENT:
        print("error: `clario dev seed` only runs with APP_ENV=development")
        return 1

    slug = service.slugify(args.workspace_name)

    async def needs_user(session: AsyncSession) -> bool:
        return await identity_repo.get_user_by_email(session, args.owner_email) is None

    password = read_password(from_stdin=args.password_stdin) if run_in_session(needs_user) else None

    async def op(session: AsyncSession) -> list[str]:
        done = []
        if password is not None:
            await service.create_user(
                session,
                email=args.owner_email,
                full_name=args.owner_name,
                password=password,
                is_platform_admin=True,
            )
            done.append(f"created user {args.owner_email} (platform admin)")
        else:
            done.append(f"user {args.owner_email} already exists")
        if await workspace_repo.get_by_slug(session, slug) is None:
            await service.create_workspace(
                session, name=args.workspace_name, owner_email=args.owner_email, slug=slug
            )
            done.append(f"created workspace {slug} (owner {args.owner_email})")
        else:
            done.append(f"workspace {slug} already exists")
        # Show every catalog card in the dev workspace, including coming-soon ones.
        registry = build_registry()
        for manifest in registry.manifests:
            if manifest.availability is Availability.COMING_SOON:
                await integration_service.set_workspace_visibility(
                    session, registry, workspace_slug=slug, key=manifest.key, visible=True
                )
        done.append("coming-soon integration cards shown in the dev workspace")
        return done

    for line in run_in_session(op):
        print(line)
    return 0


def _fixture_connection(args: argparse.Namespace) -> int:
    """Connect Zoho Books in a dev workspace without Zoho: syncs read the fixture dataset."""
    settings = get_settings()
    if settings.app_env is not AppEnv.DEVELOPMENT:
        print("error: `clario dev fixture-connection` only runs with APP_ENV=development")
        return 1

    async def op(session: AsyncSession) -> str:
        registry = build_registry()
        await integration_repo.upsert_catalog(session, registry.manifests)
        workspace = await workspace_repo.get_by_slug(session, args.workspace)
        owner = await workspace_repo.first_owner(session, workspace.id) if workspace else None
        if workspace is None or owner is None:
            return f"error: no workspace {args.workspace!r} with an owner"
        scope = await load_workspace_scope(session, workspace.id, owner)
        connection = await connection_repo.ensure_pending(session, scope, "zoho-books", "in")
        if connection.external_account_id and connection.external_account_id != FIXTURE_ACCOUNT:
            return "error: this workspace uses a real Zoho organisation; disconnect it first"
        connection.status = ConnectionStatus.CONNECTED
        connection.external_account_id = FIXTURE_ACCOUNT
        connection.external_account_name = "Fixture organisation (TEST data)"
        connection.settings = {
            "currency": "INR",
            "timezone": "Asia/Kolkata",
            "fiscal_year_start_month": 4,
        }
        connection.connected_by = owner
        connection.connected_at = connection.connected_at or utc_now()
        return f"workspace {args.workspace}: Zoho Books connected to the fixture organisation"

    message = run_in_session(op)
    print(message)
    if not message.startswith("error") and not settings.finance_fixture_source:
        print("note: set FINANCE_FIXTURE_SOURCE=true in .env so syncs read the fixture dataset")
    return 1 if message.startswith("error") else 0


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    dev = subparsers.add_parser("dev", help="Development helpers (APP_ENV=development only)")
    sub = dev.add_subparsers(dest="dev_command", required=True)
    seed = sub.add_parser("seed", help="Create a dev owner user and workspace (idempotent)")
    seed.add_argument("--owner-email", required=True)
    seed.add_argument("--owner-name", default="Clario Developer")
    seed.add_argument("--workspace-name", default="Crita Creative LLP Dev")
    seed.add_argument("--password-stdin", action="store_true")
    seed.set_defaults(func=lambda args: guarded(lambda: _seed(args)))
    fixture = sub.add_parser(
        "fixture-connection",
        help="Connect Zoho Books to fixture data (no Zoho account; needs FINANCE_FIXTURE_SOURCE)",
    )
    fixture.add_argument("--workspace", required=True, help="Workspace slug")
    fixture.set_defaults(func=lambda args: guarded(lambda: _fixture_connection(args)))
