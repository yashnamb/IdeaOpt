"""Two-tier prompt resolution for specialist agents."""

from __future__ import annotations

from pathlib import Path

import structlog

log = structlog.get_logger()

_BUILT_IN_PROMPTS_DIR = Path(__file__).parent / "prompts"


def resolve_prompt(role: str, cwd: Path) -> str:
    """Resolve a prompt for the given agent role.

    Resolution order:
    1. Project override: {cwd}/.factory/agents/{role}.md
    2. Built-in default: ideaopt/agents/prompts/{role}.md
    """
    override_path = cwd / ".factory" / "agents" / f"{role}.md"
    if override_path.exists():
        log.info("prompt_override", role=role, path=str(override_path))
        return override_path.read_text()

    default_path = _BUILT_IN_PROMPTS_DIR / f"{role}.md"
    if default_path.exists():
        log.debug("prompt_builtin", role=role, path=str(default_path))
        return default_path.read_text()

    msg = f"No prompt found for role '{role}'"
    raise FileNotFoundError(msg)
