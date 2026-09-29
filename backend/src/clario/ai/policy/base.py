"""The shared assistant policy (plan §21.3–21.5), refined from the Phase 0 evaluation prompt that
scored 36/36 grounded and 10/10 refusals. The rules live in `rules.md` (reviewed like code);
a domain adds its own instructions after them."""

from __future__ import annotations

from pathlib import Path

from clario.ai.context import AgentContext


def context_block(ctx: AgentContext, display_name: str, domain_name: str) -> str:
    others = [
        f"{m.name} ({m.domain_name}{'' if m.available else ', coming soon'})"
        for m in ctx.other_modules
    ]
    return "\n".join(
        [
            f'You are the {display_name} inside Clario for the workspace "{ctx.workspace_name}".',
            f"Your only data source is this workspace's {ctx.system_name} account "
            f'"{ctx.organisation}", reached through the tools provided.',
            "",
            "Context",
            f"- Today: {ctx.today.day} {ctx.today:%b %Y} ({ctx.timezone}). "
            f"Fiscal year: {ctx.fiscal_year}. Currency: {ctx.currency}.",
            "- Other Clario modules in this workspace, which you have NO access to: "
            + ("; ".join(others) if others else "none")
            + ".",
            f"- This session covers {domain_name} only.",
        ]
    )


RULES = (Path(__file__).with_name("rules.md")).read_text(encoding="utf-8")


def system_prompt(ctx: AgentContext, display_name: str, domain_name: str, instructions: str) -> str:
    rules = RULES.format(
        domain=domain_name,
        domain_lower=domain_name.lower(),
        workspace=ctx.workspace_name,
        system=ctx.system_name,
    )
    return f"{context_block(ctx, display_name, domain_name)}\n\n{rules}\n\n{instructions.strip()}"
