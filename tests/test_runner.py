"""Tests for agent runner with mocked subprocess."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ideaopt.agents.runner import AgentError, run_agent


@pytest.fixture()
def cwd(tmp_path: Path) -> Path:
    prompts_dir = tmp_path / "ideaopt" / "agents" / "prompts"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "encoder.md").write_text("You are a design space encoder.")
    return tmp_path


def _make_proc(stdout: bytes, returncode: int = 0, stderr: bytes = b"") -> AsyncMock:
    proc = AsyncMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.returncode = returncode
    proc.kill = MagicMock()
    proc.wait = AsyncMock()
    return proc


class TestRunAgentSuccess:
    async def test_parses_json_result(self, cwd: Path) -> None:
        payload = json.dumps({"result": "Parsed design point", "cost_usd": 0.01})
        proc = _make_proc(payload.encode())

        with patch("ideaopt.agents.runner.resolve_prompt", return_value="prompt"), \
             patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await run_agent("encoder", "test idea", cwd)

        assert result == "Parsed design point"

    async def test_returns_raw_on_non_json(self, cwd: Path) -> None:
        proc = _make_proc(b"plain text response")

        with patch("ideaopt.agents.runner.resolve_prompt", return_value="prompt"), \
             patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await run_agent("encoder", "test idea", cwd)

        assert result == "plain text response"

    async def test_passes_model_flag(self, cwd: Path) -> None:
        proc = _make_proc(json.dumps({"result": "ok"}).encode())

        with patch("ideaopt.agents.runner.resolve_prompt", return_value="prompt"), \
             patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            await run_agent("encoder", "test idea", cwd, model="sonnet")

        cmd = mock_exec.call_args[0]
        assert "--model" in cmd
        assert "sonnet" in cmd

    async def test_returns_raw_when_result_not_string(self, cwd: Path) -> None:
        payload = json.dumps({"result": {"nested": "object"}})
        proc = _make_proc(payload.encode())

        with patch("ideaopt.agents.runner.resolve_prompt", return_value="prompt"), \
             patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await run_agent("encoder", "test idea", cwd)

        assert result == payload


class TestRunAgentFailure:
    async def test_retries_on_nonzero_exit(self, cwd: Path) -> None:
        fail_proc = _make_proc(b"", returncode=1, stderr=b"error")
        ok_proc = _make_proc(json.dumps({"result": "recovered"}).encode())

        call_count = 0

        async def mock_exec(*args: object, **kwargs: object) -> AsyncMock:
            nonlocal call_count
            call_count += 1
            return fail_proc if call_count == 1 else ok_proc

        with patch("ideaopt.agents.runner.resolve_prompt", return_value="prompt"), \
             patch("asyncio.create_subprocess_exec", side_effect=mock_exec), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            result = await run_agent("encoder", "test idea", cwd)

        assert result == "recovered"
        assert call_count == 2

    async def test_raises_after_max_retries(self, cwd: Path) -> None:
        fail_proc = _make_proc(b"", returncode=1, stderr=b"persistent error")

        with patch("ideaopt.agents.runner.resolve_prompt", return_value="prompt"), \
             patch("asyncio.create_subprocess_exec", return_value=fail_proc), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(AgentError, match="failed after 3 attempts"):
                await run_agent("encoder", "test idea", cwd)

    async def test_raises_on_empty_response(self, cwd: Path) -> None:
        proc = _make_proc(b"")

        with patch("ideaopt.agents.runner.resolve_prompt", return_value="prompt"), \
             patch("asyncio.create_subprocess_exec", return_value=proc), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(AgentError, match="failed after 3 attempts"):
                await run_agent("encoder", "test idea", cwd)

    async def test_raises_on_cli_not_found(self, cwd: Path) -> None:
        with patch("ideaopt.agents.runner.resolve_prompt", return_value="prompt"), \
             patch(
                 "asyncio.create_subprocess_exec",
                 side_effect=FileNotFoundError,
             ), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(AgentError, match="not found on PATH"):
                await run_agent("encoder", "test idea", cwd)


class TestRunAgentTimeout:
    async def test_kills_process_on_timeout(self, cwd: Path) -> None:
        proc = AsyncMock()
        proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
        proc.kill = MagicMock()
        proc.wait = AsyncMock()

        async def mock_exec(*args: object, **kwargs: object) -> AsyncMock:
            return proc

        with patch("ideaopt.agents.runner.resolve_prompt", return_value="prompt"), \
             patch("asyncio.create_subprocess_exec", side_effect=mock_exec), \
             patch("asyncio.wait_for", side_effect=asyncio.TimeoutError), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(AgentError, match="failed after 3 attempts"):
                await run_agent("encoder", "test idea", cwd, timeout=1)


class TestPromptResolution:
    async def test_uses_project_override(self, cwd: Path) -> None:
        override_dir = cwd / ".factory" / "agents"
        override_dir.mkdir(parents=True)
        (override_dir / "encoder.md").write_text("Custom encoder prompt")

        proc = _make_proc(json.dumps({"result": "ok"}).encode())

        with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            await run_agent("encoder", "test idea", cwd)

        cmd = mock_exec.call_args[0]
        assert "Custom encoder prompt" in cmd

    async def test_falls_back_to_builtin(self, cwd: Path) -> None:
        builtin_dir = cwd / "builtin_prompts"
        builtin_dir.mkdir()
        (builtin_dir / "encoder.md").write_text("Built-in encoder prompt")

        proc = _make_proc(json.dumps({"result": "ok"}).encode())

        with patch(
            "ideaopt.agents.prompt_resolver._BUILT_IN_PROMPTS_DIR", builtin_dir
        ), patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            await run_agent("encoder", "test idea", cwd)

        cmd = mock_exec.call_args[0]
        assert "Built-in encoder prompt" in cmd

    async def test_raises_for_unknown_role(self, cwd: Path) -> None:
        with pytest.raises(FileNotFoundError, match="No prompt found"):
            await run_agent("nonexistent_role", "test idea", cwd)
