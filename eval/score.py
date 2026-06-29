#!/usr/bin/env python3
"""Eval score script for ideaopt.

Runs all eval dimensions and outputs a composite JSON score.
Exit code 0 = pass, 1 = fail.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_command(cmd: str, timeout: int = 120) -> tuple[int, str]:
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return 1, "TIMEOUT"
    except Exception as e:
        return 1, str(e)


def score_tests() -> dict:
    rc, output = run_command("python -m pytest tests/ -q --tb=short")
    if rc == 0:
        return {"score": 1.0, "detail": "All tests pass"}
    if rc == 5:
        return {"score": 0.0, "detail": "No tests found"}
    lines = output.strip().splitlines()
    for line in reversed(lines):
        if "passed" in line and "failed" in line:
            parts = line.split()
            for i, p in enumerate(parts):
                if p == "passed" and i > 0:
                    passed = int(parts[i - 1])
                if p == "failed," and i > 0:
                    failed = int(parts[i - 1])
            total = passed + failed
            return {
                "score": round(passed / total, 3) if total > 0 else 0.0,
                "detail": f"{passed}/{total} tests pass",
            }
        if "passed" in line:
            return {"score": 1.0, "detail": line.strip()}
    return {"score": 0.0, "detail": output[-500:] if output else "Tests failed"}


def score_lint() -> dict:
    rc, output = run_command("python -m ruff check ideaopt/ --output-format=json")
    if rc == 0:
        return {"score": 1.0, "detail": "No lint errors"}
    try:
        errors = json.loads(output)
        count = len(errors)
        score = max(0.0, 1.0 - count * 0.05)
        return {"score": round(score, 3), "detail": f"{count} lint errors"}
    except (json.JSONDecodeError, TypeError):
        if "No such file or directory" in output or "No module named" in output:
            return {"score": 0.0, "detail": "ruff not installed or ideaopt/ not found"}
        return {"score": 0.0, "detail": f"Lint failed: {output[:200]}"}


def score_type_check() -> dict:
    rc, output = run_command(
        "python -m mypy ideaopt/ --ignore-missing-imports"
    )
    if rc == 0:
        return {"score": 1.0, "detail": "No type errors"}
    lines = output.strip().splitlines()
    error_count = 0
    for line in lines:
        if ": error:" in line:
            error_count += 1
    if error_count > 0:
        score = max(0.0, 1.0 - error_count * 0.05)
        return {"score": round(score, 3), "detail": f"{error_count} type errors"}
    if "No module named" in output or "cannot find" in output:
        return {"score": 0.0, "detail": "mypy not installed or ideaopt/ not found"}
    return {"score": 0.0, "detail": output[:200]}


def score_importable(module_path: str, label: str) -> dict:
    rc, output = run_command(f'python -c "import {module_path}"')
    if rc == 0:
        return {"score": 1.0, "detail": f"{label} importable"}
    return {"score": 0.0, "detail": f"{label} not importable: {output[:200]}"}


def score_models() -> dict:
    rc, output = run_command(
        'python -c "'
        "from ideaopt.models import ("
        "DesignPoint, CandidateHypothesis, EvalScore, "
        "ScoredCandidate, RunConfig"
        '); print(\'OK\')"'
    )
    if rc == 0:
        return {"score": 1.0, "detail": "All domain models importable"}
    return {"score": 0.0, "detail": f"Models import failed: {output[:200]}"}


def score_cli() -> dict:
    rc, output = run_command("python -m ideaopt.cli --help")
    if rc == 0:
        return {"score": 1.0, "detail": "CLI entry point works"}
    return {"score": 0.0, "detail": f"CLI failed: {output[:200]}"}


def score_agent_prompts() -> dict:
    prompts_dir = PROJECT_ROOT / "ideaopt" / "agents" / "prompts"
    required = [
        "encoder.md",
        "generator.md",
        "validator.md",
        "competitor.md",
        "customer_discovery.md",
        "merger.md",
        "report.md",
    ]
    if not prompts_dir.is_dir():
        return {"score": 0.0, "detail": "prompts directory not found"}
    found = [r for r in required if (prompts_dir / r).is_file()]
    score = len(found) / len(required)
    missing = [r for r in required if r not in found]
    detail = f"{len(found)}/{len(required)} prompts found"
    if missing:
        detail += f", missing: {', '.join(missing)}"
    return {"score": round(score, 3), "detail": detail}


def score_scoring_module() -> dict:
    return score_importable(
        "ideaopt.scoring", "Scoring module"
    )


def score_agent_runner() -> dict:
    return score_importable(
        "ideaopt.agents.runner", "Agent runner"
    )


DIMENSIONS = [
    ("tests", 0.30, score_tests),
    ("lint", 0.15, score_lint),
    ("type_check", 0.10, score_type_check),
    ("models_valid", 0.10, score_models),
    ("cli_entry", 0.10, score_cli),
    ("agent_prompts", 0.10, score_agent_prompts),
    ("scoring_logic", 0.10, score_scoring_module),
    ("agent_runner", 0.05, score_agent_runner),
]


def main() -> None:
    results = []
    total_score = 0.0
    total_weight = 0.0

    for name, weight, scorer in DIMENSIONS:
        try:
            result = scorer()
        except Exception as e:
            result = {"score": 0.0, "detail": f"Error: {e}"}

        result["name"] = name
        result["weight"] = weight
        result["passed"] = result["score"] >= 0.5
        result["details"] = result.pop("detail")
        results.append(result)
        total_score += result["score"] * weight
        total_weight += weight

    normalized = round(total_score / total_weight, 4) if total_weight > 0 else 0.0

    output = {
        "score": normalized,
        "passed": normalized >= 0.5,
        "results": results,
        "guard_violations": [],
    }

    print(json.dumps(output, indent=2))
    sys.exit(0 if output["passed"] else 1)


if __name__ == "__main__":
    main()
