"""Main exploration loop: Generate → Evaluate → Select → Merge → Refine."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TypeVar

import structlog
from pydantic import BaseModel, ValidationError

from ideaopt.agents.runner import AgentError, run_agent
from ideaopt.budget import BudgetTracker
from ideaopt.models import (
    CandidateHypothesis,
    DesignPoint,
    EvalScore,
    ExplorationReport,
    IterationResult,
    ReportState,
    RunConfig,
    ScoredCandidate,
)
from ideaopt.scoring import score_candidate, select_top_k

log = structlog.get_logger()


def _update_report(path: Path | None, state: ReportState) -> None:
    if path is None:
        return
    from ideaopt.visualizer import generate_html
    path.write_text(generate_html(state))


async def run_exploration(
    idea: str, config: RunConfig, *, report_path: Path | None = None,
) -> ExplorationReport:
    """Run the full design-space exploration loop."""
    cwd = Path.cwd()
    budget = BudgetTracker(
        max_iterations=config.max_iterations,
        max_agent_calls=config.max_agent_calls,
    )

    log.info("exploration_start", idea=idea[:80], config=config.model_dump())

    design_point = await _encode(idea, cwd, budget, config)
    _update_report(report_path, ReportState(
        status="encoding", original_idea=idea, design_point=design_point,
    ))
    iterations: list[IterationResult] = []
    prev_best_summary: str | None = None
    prev_best_score: float | None = None
    stagnation_count = 0

    while budget.can_continue():
        iteration_num = budget.iterations_completed + 1
        log.info("iteration_start", iteration=iteration_num)

        candidates = await _generate(
            idea, design_point, iteration_num, iterations, cwd, budget, config,
        )
        if not candidates:
            log.warning("no_candidates_generated", iteration=iteration_num)
            break

        _update_report(report_path, ReportState(
            status="generating", original_idea=idea, design_point=design_point,
            iterations=iterations, current_iteration=iteration_num,
            current_candidates=candidates,
        ))

        scored = await _evaluate_and_score(
            candidates, idea, design_point, cwd, budget, config,
        )
        if not scored:
            log.warning("no_candidates_scored", iteration=iteration_num)
            break

        _update_report(report_path, ReportState(
            status="evaluating", original_idea=idea, design_point=design_point,
            iterations=iterations, current_iteration=iteration_num,
            current_candidates=candidates, current_scored=scored,
        ))

        top_k = select_top_k(scored, config.top_k)
        log.info(
            "top_k_selected",
            iteration=iteration_num,
            scores=[round(sc.final_score, 3) for sc in top_k],
        )

        merged = await _merge(idea, top_k, iteration_num, cwd, budget, config)

        if merged and budget.can_continue():
            merged_scored_list = await _evaluate_and_score(
                [merged], idea, design_point, cwd, budget, config,
            )
            if merged_scored_list:
                scored.extend(merged_scored_list)
                top_k = select_top_k(scored, config.top_k)

        _update_report(report_path, ReportState(
            status="merging", original_idea=idea, design_point=design_point,
            iterations=iterations, current_iteration=iteration_num,
            current_candidates=candidates, current_scored=scored,
        ))

        iteration_result = IterationResult(
            iteration=iteration_num,
            candidates=candidates,
            scored_candidates=scored,
            merged_candidate=merged,
        )
        iterations.append(iteration_result)
        budget.complete_iteration()

        best = top_k[0]
        stop_reason = _check_stop_conditions(
            best, prev_best_summary, prev_best_score, stagnation_count, budget,
        )
        if stop_reason:
            log.info("exploration_stop", reason=stop_reason, iteration=iteration_num)
            break

        if prev_best_summary == best.candidate.summary:
            stagnation_count += 1
        else:
            stagnation_count = 0
        prev_best_summary = best.candidate.summary
        prev_best_score = best.final_score

    all_scored = [sc for it in iterations for sc in it.scored_candidates]
    best_candidate = select_top_k(all_scored, 1)[0] if all_scored else _fallback_scored(
        design_point, idea,
    )

    validation = _extract_validation(best_candidate)

    report = ExplorationReport(
        original_idea=idea,
        design_point=design_point,
        iterations=iterations,
        best_candidate=best_candidate,
        validation_experiment=validation,
        budget_summary=budget.summary(),
    )
    _update_report(report_path, ReportState(
        status="complete", original_idea=idea, design_point=design_point,
        iterations=iterations, current_iteration=len(iterations),
        best_candidate=best_candidate, validation_experiment=validation,
        budget_summary=budget.summary(),
    ))

    log.info(
        "exploration_complete",
        iterations=len(iterations),
        best_score=round(best_candidate.final_score, 3),
        budget=budget.summary().model_dump(),
    )
    return report


async def _encode(
    idea: str, cwd: Path, budget: BudgetTracker, config: RunConfig,
) -> DesignPoint:
    task = json.dumps({"idea": idea})
    start = time.monotonic()
    try:
        raw = await run_agent("encoder", task, cwd, model=config.model, timeout=config.agent_timeout)
        budget.track_call("encoder", time.monotonic() - start, success=True)
    except AgentError:
        budget.track_call("encoder", time.monotonic() - start, success=False)
        raise

    return _parse_model(raw, DesignPoint)


async def _generate(
    idea: str,
    design_point: DesignPoint,
    iteration: int,
    prev_iterations: list[IterationResult],
    cwd: Path,
    budget: BudgetTracker,
    config: RunConfig,
) -> list[CandidateHypothesis]:
    prev_scores: list[dict[str, object]] = []
    for it in prev_iterations:
        for sc in it.scored_candidates:
            prev_scores.append({
                "summary": sc.candidate.summary,
                "final_score": sc.final_score,
                "eval_scores": sc.eval_scores.model_dump(),
            })

    task = json.dumps({
        "original_idea": idea,
        "design_point": design_point.model_dump(),
        "iteration": iteration,
        "candidates_requested": config.candidates_per_round,
        "previous_scores": prev_scores,
    })

    start = time.monotonic()
    try:
        raw = await run_agent("generator", task, cwd, model=config.model, timeout=config.agent_timeout)
        budget.track_call("generator", time.monotonic() - start, success=True)
    except AgentError:
        budget.track_call("generator", time.monotonic() - start, success=False)
        raise

    return _parse_candidates(raw, iteration)


async def _evaluate_candidate(
    candidate: CandidateHypothesis,
    idea: str,
    role: str,
    cwd: Path,
    budget: BudgetTracker,
    config: RunConfig,
) -> EvalScore | None:
    task = json.dumps({
        "original_idea": idea,
        "candidate": candidate.model_dump(),
    })

    start = time.monotonic()
    try:
        raw = await run_agent(role, task, cwd, model=config.model, timeout=config.agent_timeout)
        budget.track_call(role, time.monotonic() - start, success=True)
        return _parse_model(raw, EvalScore)
    except (AgentError, ValueError) as exc:
        budget.track_call(role, time.monotonic() - start, success=False)
        log.warning("evaluator_failed", role=role, candidate=candidate.summary[:60], error=str(exc))
        return None


async def _evaluate_and_score(
    candidates: list[CandidateHypothesis],
    idea: str,
    original: DesignPoint,
    cwd: Path,
    budget: BudgetTracker,
    config: RunConfig,
) -> list[ScoredCandidate]:
    import asyncio

    scored: list[ScoredCandidate] = []
    evaluator_roles = ["validator", "competitor", "customer_discovery"]

    for candidate in candidates:
        if not budget.can_continue():
            log.warning("budget_exhausted_during_eval", evaluated_so_far=len(scored))
            break

        evals = await asyncio.gather(
            *[
                _evaluate_candidate(candidate, idea, role, cwd, budget, config)
                for role in evaluator_roles
            ],
            return_exceptions=True,
        )

        partial_scores: list[EvalScore] = []
        for i, result in enumerate(evals):
            if isinstance(result, EvalScore):
                partial_scores.append(result)
            elif isinstance(result, Exception):
                log.warning(
                    "evaluator_exception",
                    role=evaluator_roles[i],
                    error=str(result),
                )

        if not partial_scores:
            log.warning("all_evaluators_failed", candidate=candidate.summary[:60])
            continue

        merged_eval = _merge_eval_scores(partial_scores)
        sc = score_candidate(candidate, merged_eval, original, config)
        scored.append(sc)

    return scored


def _merge_eval_scores(scores: list[EvalScore]) -> EvalScore:
    """Average across multiple evaluator scores."""
    n = len(scores)
    rationales = [s.rationale for s in scores]
    return EvalScore(
        pain=sum(s.pain for s in scores) / n,
        specificity=sum(s.specificity for s in scores) / n,
        differentiation=sum(s.differentiation for s in scores) / n,
        testability=sum(s.testability for s in scores) / n,
        feasibility=sum(s.feasibility for s in scores) / n,
        rationale=" | ".join(rationales),
    )


async def _merge(
    idea: str,
    top_k: list[ScoredCandidate],
    iteration: int,
    cwd: Path,
    budget: BudgetTracker,
    config: RunConfig,
) -> CandidateHypothesis | None:
    if len(top_k) < 2:
        return None

    task = json.dumps({
        "original_idea": idea,
        "candidates": [sc.model_dump() for sc in top_k],
        "iteration": iteration,
    })

    start = time.monotonic()
    try:
        raw = await run_agent("merger", task, cwd, model=config.model, timeout=config.agent_timeout)
        budget.track_call("merger", time.monotonic() - start, success=True)
    except AgentError as exc:
        budget.track_call("merger", time.monotonic() - start, success=False)
        log.warning("merger_failed", error=str(exc))
        return None

    try:
        return _parse_model(raw, CandidateHypothesis)
    except ValueError as exc:
        log.warning("merger_parse_failed", error=str(exc))
        return None


def _check_stop_conditions(
    best: ScoredCandidate,
    prev_best_summary: str | None,
    prev_best_score: float | None,
    stagnation_count: int,
    budget: BudgetTracker,
) -> str | None:
    if not budget.can_continue():
        return "budget_exhausted"

    if prev_best_score is not None:
        improvement = best.final_score - prev_best_score
        if improvement < 0.5:
            return f"score_plateau (improvement={improvement:.3f} < 0.5)"

    if stagnation_count >= 1 and prev_best_summary == best.candidate.summary:
        return "same_best_candidate_2_consecutive_rounds"

    return None


def _extract_validation(best: ScoredCandidate) -> str:
    rationale = best.eval_scores.rationale
    if rationale:
        return rationale
    return "No validation experiment available — run customer discovery manually."


def _fallback_scored(design_point: DesignPoint, idea: str) -> ScoredCandidate:
    candidate = CandidateHypothesis(
        design_point=design_point,
        summary=idea,
        rationale="Original idea (no iterations completed)",
        iteration=0,
    )
    default_eval = EvalScore(
        pain=5.0, specificity=5.0, differentiation=5.0,
        testability=5.0, feasibility=5.0,
        rationale="Default scores — no evaluation performed.",
    )
    return ScoredCandidate(
        candidate=candidate,
        eval_scores=default_eval,
        composite_score=5.0,
        drift_score=0.0,
        complexity_score=0.0,
        final_score=5.0,
    )


_T = TypeVar("_T", bound=BaseModel)


def _parse_model(raw: str, model_cls: type[_T]) -> _T:
    """Parse raw agent output into a Pydantic model."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        cleaned = _extract_json(raw)
        if cleaned is None:
            raise ValueError(f"Cannot parse JSON from agent output: {raw[:200]}")
        data = json.loads(cleaned)

    try:
        return model_cls.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"Validation failed for {model_cls.__name__}: {exc}") from exc


def _parse_candidates(raw: str, iteration: int) -> list[CandidateHypothesis]:
    """Parse a JSON array of candidate hypotheses."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        cleaned = _extract_json(raw)
        if cleaned is None:
            raise ValueError(f"Cannot parse candidates JSON: {raw[:200]}")
        data = json.loads(cleaned)

    if isinstance(data, dict) and "candidates" in data:
        data = data["candidates"]
    if not isinstance(data, list):
        raise ValueError(f"Expected list of candidates, got {type(data).__name__}")

    candidates = []
    for item in data:
        if isinstance(item, dict) and "iteration" not in item:
            item["iteration"] = iteration
        try:
            candidates.append(CandidateHypothesis.model_validate(item))
        except ValidationError as exc:
            log.warning("candidate_parse_failed", error=str(exc))
    return candidates


def _extract_json(raw: str) -> str | None:
    """Try to extract JSON from text that may contain markdown fences."""
    for start_marker in ("```json", "```"):
        if start_marker in raw:
            start = raw.index(start_marker) + len(start_marker)
            end = raw.index("```", start) if "```" in raw[start:] else len(raw)
            return raw[start:end].strip()

    for char in ("{", "["):
        if char in raw:
            return raw[raw.index(char):]
    return None
