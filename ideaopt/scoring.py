"""Composite scoring with drift penalty: S(x) = R(x;E) - λD(x,x₀) - μC(x)."""

from __future__ import annotations

import structlog

from ideaopt.models import (
    CandidateHypothesis,
    DesignPoint,
    EvalScore,
    RunConfig,
    ScoredCandidate,
)

log = structlog.get_logger()

REWARD_WEIGHTS: dict[str, float] = {
    "pain": 0.30,
    "specificity": 0.20,
    "differentiation": 0.20,
    "testability": 0.15,
    "feasibility": 0.15,
}

DESIGN_POINT_FIELDS: list[str] = [
    "customer",
    "problem",
    "solution",
    "value_prop",
    "wedge",
    "business_model",
    "gtm_path",
]


def compute_reward(eval_scores: EvalScore) -> float:
    """Weighted average of evaluation scores, normalized to 0-10."""
    total = 0.0
    for field, weight in REWARD_WEIGHTS.items():
        total += getattr(eval_scores, field) * weight
    return total


def compute_drift(candidate: CandidateHypothesis, original: DesignPoint) -> float:
    """Dimension-by-dimension comparison of how far each field moved from the original.

    Returns a value in [0, 1] where 0 means identical and 1 means completely different.
    Uses simple string equality per dimension — a changed field scores 1, unchanged scores 0.
    """
    changed = 0
    for field in DESIGN_POINT_FIELDS:
        original_val = getattr(original, field)
        candidate_val = getattr(candidate.design_point, field)
        if original_val != candidate_val:
            changed += 1
    return changed / len(DESIGN_POINT_FIELDS)


def compute_complexity(candidate: CandidateHypothesis) -> float:
    """Penalize kitchen-sink ideas. Higher score = more complex.

    Heuristic: longer descriptions across dimensions indicate over-scoped ideas.
    Returns a value in [0, 1].
    """
    lengths = []
    for field in DESIGN_POINT_FIELDS:
        val = getattr(candidate.design_point, field)
        lengths.append(len(val))

    avg_length = sum(lengths) / len(lengths) if lengths else 0.0
    # Normalize: 200 chars average per field is the "fully complex" threshold
    return min(1.0, avg_length / 200.0)


def score_candidate(
    candidate: CandidateHypothesis,
    eval_scores: EvalScore,
    original: DesignPoint,
    config: RunConfig,
) -> ScoredCandidate:
    """Compute S(x) = R(x;E) - λD(x,x₀) - μC(x) and return a ScoredCandidate."""
    reward = compute_reward(eval_scores)
    drift = compute_drift(candidate, original)
    complexity = compute_complexity(candidate)

    # Scale drift and complexity penalties to the same 0-10 range as reward
    final = reward - config.drift_weight * drift * 10.0 - config.complexity_weight * complexity * 10.0

    log.debug(
        "scored_candidate",
        summary=candidate.summary[:60],
        reward=round(reward, 3),
        drift=round(drift, 3),
        complexity=round(complexity, 3),
        final=round(final, 3),
    )

    return ScoredCandidate(
        candidate=candidate,
        eval_scores=eval_scores,
        composite_score=reward,
        drift_score=drift,
        complexity_score=complexity,
        final_score=final,
    )


def select_top_k(scored_candidates: list[ScoredCandidate], k: int) -> list[ScoredCandidate]:
    """Select the top-k candidates by final_score, descending."""
    sorted_candidates = sorted(scored_candidates, key=lambda sc: sc.final_score, reverse=True)
    return sorted_candidates[:k]
