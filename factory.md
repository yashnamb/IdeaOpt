# Factory Configuration
<!-- This file configures the Remote Factory for your project. -->
<!-- The factory reads this during Init mode and generates .factory/config.json from it. -->
<!-- Fill in each section below. -->

## Goal
<!-- A single sentence describing what this project should achieve. -->

A multi-agent design space exploration harness that takes an initial startup idea, generates candidate startup hypotheses, evaluates them across multiple axes, merges the strongest components, and iteratively refines the idea under a fixed budget.

## Scope

### Modifiable
<!-- Files and directories the factory is allowed to create or edit. -->
<!-- One path per line. Glob patterns are supported. -->

- ideaopt/**/*.py
- ideaopt/agents/prompts/*.md
- tests/**/*.py

### Read-only
<!-- Files the factory may read but must never modify. -->

- idea.md
- pyproject.toml
- CLAUDE.md

## Guards
<!-- Rules the factory must never violate. Checked before every commit. -->

- Do not delete or overwrite existing tests
- Do not modify files outside the declared scope
- Do not introduce secrets or credentials into the repository
- Do not modify eval/score.py or .factory/ directory

## Eval

### Command
<!-- The shell command the factory runs to score a change. -->
<!-- It must output JSON to stdout matching the EvalResult format. -->

```bash
python eval/score.py
```

### Threshold
<!-- Minimum composite score (0.0-1.0) required to keep a change. -->

0.8

## Target Branch
<!-- Branch that experiment PRs target. Default: main -->
<!-- Set to a different branch (e.g. factory/dev) to stage factory changes before merging to main -->

main

## Smoke Test
<!-- Optional shell command that must pass before any change is kept. -->
<!-- If configured, this runs as part of `factory precheck` — failure = mandatory revert. -->

```bash
python -m ideaopt --help && python -c 'from ideaopt.orchestrator import run_exploration; print("OK")'
```

## Constraints
<!-- Soft rules that guide behavior but don't block commits. -->

- Prefer small, incremental changes over large rewrites
- Each change should be accompanied by at least one test
- Follow the existing code style and conventions
- All agent invocation must use Claude Code CLI subprocess, not the Anthropic Python SDK
- Use Pydantic v2 strict mode for all domain models
