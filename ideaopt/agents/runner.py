"""Core agent runner — invokes Claude Code as an async subprocess."""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

import structlog

from ideaopt.agents.prompt_resolver import resolve_prompt

log = structlog.get_logger()

_MAX_RETRIES = 2
_BACKOFF_BASE = 2.0


async def run_agent(
    role: str,
    task: str,
    cwd: Path,
    *,
    model: str | None = None,
    timeout: int = 300,
) -> str:
    """Spawn a Claude Code subprocess for the given agent role.

    Retries up to _MAX_RETRIES times with exponential backoff on failure.
    Returns the parsed text result from Claude Code's JSON output.
    """
    prompt = resolve_prompt(role, cwd)

    cmd = [
        "claude",
        "--append-system-prompt",
        prompt,
        "-p",
        task,
        "--output-format",
        "json",
        "--dangerously-skip-permissions",
    ]
    if model:
        cmd.extend(["--model", model])

    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        if attempt > 0:
            wait = _BACKOFF_BASE**attempt
            log.info("agent_retry", role=role, attempt=attempt, backoff_seconds=wait)
            await asyncio.sleep(wait)

        start = time.monotonic()
        try:
            result = await _invoke(cmd, cwd, timeout)
            duration = time.monotonic() - start
            log.info(
                "agent_completed",
                role=role,
                duration=round(duration, 2),
                result_length=len(result),
            )
            return result
        except (asyncio.TimeoutError, AgentError) as exc:
            duration = time.monotonic() - start
            last_error = exc
            log.warning(
                "agent_failed",
                role=role,
                attempt=attempt + 1,
                duration=round(duration, 2),
                error=str(exc),
            )

    raise AgentError(
        f"Agent '{role}' failed after {_MAX_RETRIES + 1} attempts: {last_error}"
    )


async def _invoke(cmd: list[str], cwd: Path, timeout: int) -> str:
    """Run the subprocess and parse the JSON response."""
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd),
            env=env,
        )
    except FileNotFoundError:
        raise AgentError("Claude Code CLI ('claude') not found on PATH") from None

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise

    if proc.returncode != 0:
        stderr_text = stderr_bytes.decode(errors="replace").strip() if stderr_bytes else ""
        raise AgentError(
            f"claude exited with code {proc.returncode}: {stderr_text[:500]}"
        )

    return _parse_response(stdout_bytes)


def _parse_response(stdout_bytes: bytes) -> str:
    """Extract the result text from Claude Code's JSON output."""
    raw = stdout_bytes.decode(errors="replace").strip()
    if not raw:
        raise AgentError("Empty response from Claude Code")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw

    if isinstance(data, dict):
        result = data.get("result", raw)
        return result if isinstance(result, str) else raw

    return raw


class AgentError(Exception):
    """Raised when an agent subprocess fails."""
