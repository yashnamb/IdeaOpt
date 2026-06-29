# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Build & Run

```bash
uv sync --group dev          # install deps
uv run ideaopt run "idea" # run exploration
```

## Test

```bash
uv run python -m pytest tests/ -q
```

## Lint & Type Check

```bash
uv run python -m ruff check ideaopt/
uv run python -m mypy ideaopt/
```

## Style

- Python 3.11+, PEP 604 unions (`X | Y` not `Union`)
- `from __future__ import annotations` in every module
- Snake_case everywhere
- 100 char line length (ruff enforced)
- All Pydantic models: `ConfigDict(strict=True, extra="forbid")`
- Async/await by default; CLI wraps with `asyncio.run()`
- Structured logging: `log = structlog.get_logger()` at module level
- No comments unless the WHY is non-obvious

## Architecture

Three-layer separation:

1. **Layer 1 — Python CLI** (`ideaopt/cli.py`): Pure tools, no decision logic
2. **Layer 2 — Orchestrator** (`ideaopt/orchestrator.py`): Generate→Evaluate→Select→Merge→Refine loop
3. **Layer 3 — Specialist Agents** (`ideaopt/agents/runner.py`): Claude Code subprocesses

Agent invocation is via Claude Code CLI subprocess, NOT the Anthropic SDK.

## Key Models

All in `ideaopt/models.py`: DesignPoint, CandidateHypothesis, EvalScore, ScoredCandidate, RunConfig, IterationResult, ExplorationReport.

## Scoring

Composite score: `S(x) = R(x;E) - λD(x,x₀) - μC(x)` where R = reward, D = drift from original, C = complexity penalty.

## State Persistence

File-based JSON/JSONL. No database.
