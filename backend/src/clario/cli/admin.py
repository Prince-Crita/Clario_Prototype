"""`clario admin …` — provisioning for Crita staff (plan §12: no public sign-up, ADR-012).

Every command runs in one transaction and writes audit rows (actor_type `system`).
"""

from __future__ import annotations

import argparse

from sqlalchemy.ext.asyncio import AsyncSession

from clario.api.registry import build_registry
from clario.cli._support import guarded, read_password, run_in_session
from clario.platform.access.permissions import Role
from clario.platform.identity.models import UserStatus
from clario.platform.integrations import service as integration_service
from clario.platform.workspaces import repository as workspace_repo
from clario.platform.workspaces import service
from clario.platform.workspaces.models import WorkspaceStatus


def _create_user(args: argparse.Namespace) -> int:
    password = read_password(from_stdin=args.password_stdin)

    async def op(session: AsyncSession) -> str:
        user = await service.create_user(
            session,
            email=args.email,
            full_name=args.name,
            password=password,
            is_platform_admin=args.platform_admin,
        )
        return user.email

    print(f"Created user {run_in_session(op)}")
    return 0


def _create_workspace(args: argparse.Namespace) -> int:
    async def op(session: AsyncSession) -> tuple[str, str]:
        workspace = await service.create_workspace(
            session,
            name=args.name,
            owner_email=args.owner_email,
            slug=args.slug,
            timezone=args.timezone,
            base_currency=args.currency,
            fiscal_year_start_month=args.fy_start_month,
        )
        return workspace.slug, str(workspace.id)

    slug, workspace_id = run_in_session(op)
    print(f"Created workspace {slug} ({workspace_id}); owner {args.owner_email}")
    return 0


def _set_role(args: argparse.Namespace) -> int:
    async def op(session: AsyncSession) -> None:
        await service.set_member_role(
            session, workspace_slug=args.workspace, email=args.email, role=Role(args.role)
        )

    run_in_session(op)
    print(f"{args.email} is now {args.role} in {args.workspace}")
    return 0


def _remove_member(args: argparse.Namespace) -> int:
    async def op(session: AsyncSession) -> None:
        await service.remove_member(session, workspace_slug=args.workspace, email=args.email)

    run_in_session(op)
    print(f"Removed {args.email} from {args.workspace}")
    return 0


def _set_workspace_status(args: argparse.Namespace) -> int:
    async def op(session: AsyncSession) -> None:
        await service.set_workspace_status(
            session, workspace_slug=args.workspace, status=WorkspaceStatus(args.status)
        )

    run_in_session(op)
    print(f"Workspace {args.workspace} is now {args.status}")
    return 0


def _set_user_status(status: UserStatus) -> object:
    def handler(args: argparse.Namespace) -> int:
        async def op(session: AsyncSession) -> None:
            await service.set_user_status(session, email=args.email, status=status)

        run_in_session(op)
        print(
            f"User {args.email} is now {status.value}"
            + (" (all sessions revoked)" if status == UserStatus.DISABLED else "")
        )
        return 0

    return handler


def _reset_password(args: argparse.Namespace) -> int:
    password = read_password(from_stdin=args.password_stdin, prompt="New password")

    async def op(session: AsyncSession) -> None:
        await service.reset_password(session, email=args.email, new_password=password)

    run_in_session(op)
    print(f"Password reset for {args.email}; lockout cleared; all sessions revoked")
    return 0


def _list_workspaces(_: argparse.Namespace) -> int:
    async def op(session: AsyncSession) -> list[tuple[str, str, str, int]]:
        return await workspace_repo.list_all_for_operators(session)

    rows = run_in_session(op)
    if not rows:
        print("No workspaces.")
    for slug, name, status, members in rows:
        print(f"{slug:32} {status:10} {members:3} member(s)  {name}")
    return 0


def _set_integration_visibility(args: argparse.Namespace) -> int:
    registry = build_registry()

    async def op(session: AsyncSession) -> str:
        manifest = await integration_service.set_workspace_visibility(
            session,
            registry,
            workspace_slug=args.workspace,
            key=args.integration,
            visible=args.visible,
        )
        return manifest.name

    name = run_in_session(op)
    print(f"{name} is now {'shown' if args.visible else 'hidden'} in {args.workspace}")
    return 0


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    admin = subparsers.add_parser("admin", help="Provision users and workspaces (Crita staff)")
    sub = admin.add_subparsers(dest="admin_command", required=True)

    def add(name: str, handler: object, help_text: str) -> argparse.ArgumentParser:
        parser = sub.add_parser(name, help=help_text)
        parser.set_defaults(func=lambda args: guarded(lambda: handler(args)))  # type: ignore[operator]
        return parser

    p = add("create-user", _create_user, "Create a user (password prompted)")
    p.add_argument("--email", required=True)
    p.add_argument("--name", required=True, help="Full name")
    p.add_argument("--platform-admin", action="store_true", help="Crita staff operator account")
    p.add_argument(
        "--password-stdin", action="store_true", help="Read the password from standard input"
    )

    p = add("create-workspace", _create_workspace, "Create a client workspace with an owner")
    p.add_argument("--name", required=True)
    p.add_argument("--owner-email", required=True)
    p.add_argument("--slug", help="Defaults to a slug of the name")
    p.add_argument("--timezone", default="Asia/Kolkata")
    p.add_argument("--currency", default="INR")
    p.add_argument("--fy-start-month", type=int, default=4, choices=range(1, 13), metavar="1-12")

    p = add("set-role", _set_role, "Add a user to a workspace or change their role")
    p.add_argument("--workspace", required=True, help="Workspace slug")
    p.add_argument("--email", required=True)
    p.add_argument("--role", required=True, choices=[r.value for r in Role])

    p = add("remove-member", _remove_member, "Remove a user from a workspace")
    p.add_argument("--workspace", required=True)
    p.add_argument("--email", required=True)

    p = add(
        "set-workspace-status", _set_workspace_status, "Activate, suspend or archive a workspace"
    )
    p.add_argument("--workspace", required=True)
    p.add_argument("--status", required=True, choices=[s.value for s in WorkspaceStatus])

    p = add(
        "disable-user",
        _set_user_status(UserStatus.DISABLED),
        "Disable a user and sign them out everywhere",
    )
    p.add_argument("--email", required=True)
    p = add("enable-user", _set_user_status(UserStatus.ACTIVE), "Re-enable a disabled user")
    p.add_argument("--email", required=True)

    p = add("reset-password", _reset_password, "Set a new password, clear lockout, revoke sessions")
    p.add_argument("--email", required=True)
    p.add_argument("--password-stdin", action="store_true")

    add("list-workspaces", _list_workspaces, "List all workspaces (operator view)")

    p = add(
        "set-integration-visibility",
        _set_integration_visibility,
        "Show or hide an integration card for one workspace (e.g. a coming-soon system)",
    )
    p.add_argument("--workspace", required=True, help="Workspace slug")
    p.add_argument(
        "--integration", required=True, help="Integration key, e.g. city-threads-inventory"
    )
    shown = p.add_mutually_exclusive_group(required=True)
    shown.add_argument("--visible", dest="visible", action="store_true")
    shown.add_argument("--hidden", dest="visible", action="store_false")
