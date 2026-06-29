"""Tests for ideaopt scoring functions."""

from __future__ import annotations

from ideaopt.models import (
    CandidateHypothesis,
    DesignPoint,
    EvalScore,
    RunConfig,
    ScoredCandidate,
)
from ideaopt.scoring import (
    REWARD_WEIGHTS,
    compute_complexity,
    compute_drift,
    compute_reward,
    score_candidate,
    select_top_k,
)


def _make_design_point(**overrides: str) -> DesignPoint:
    defaults = {
        "customer": "Solo dentists",
        "problem": "Missed calls",
        "solution": "AI receptionist",
        "value_prop": "Never miss a call",
        "wedge": "After-hours calls",
        "business_model": "$299/mo",
        "gtm_path": "Direct outreach",
    }
    defaults.update(overrides)
    return DesignPoint(**defaults)


def _make_candidate(
    iteration: int = 0,
    summary: str = "Test candidate",
    **dp_overrides: str,
) -> CandidateHypothesis:
    return CandidateHypothesis(
        design_point=_make_design_point(**dp_overrides),
        summary=summary,
        rationale="Test rationale",
        iteration=iteration,
    )


def _make_eval_scores(
    pain: float = 8.0,
    specificity: float = 7.0,
    differentiation: float = 6.0,
    testability: float = 9.0,
    feasibility: float = 7.5,
) -> EvalScore:
    return EvalScore(
        pain=pain,
        specificity=specificity,
        differentiation=differentiation,
        testability=testability,
        feasibility=feasibility,
        rationale="Test rationale",
    )


class TestComputeReward:
    def test_known_inputs(self) -> None:
        es = _make_eval_scores(pain=8.0, specificity=7.0, differentiation=6.0,
                               testability=9.0, feasibility=7.5)
        reward = compute_reward(es)
        expected = (8.0 * 0.30 + 7.0 * 0.20 + 6.0 * 0.20 + 9.0 * 0.15 + 7.5 * 0.15)
        assert abs(reward - expected) < 1e-9

    def test_all_zeros(self) -> None:
        es = _make_eval_scores(pain=0.0, specificity=0.0, differentiation=0.0,
                               testability=0.0, feasibility=0.0)
        assert compute_reward(es) == 0.0

    def test_all_tens(self) -> None:
        es = _make_eval_scores(pain=10.0, specificity=10.0, differentiation=10.0,
                               testability=10.0, feasibility=10.0)
        assert abs(compute_reward(es) - 10.0) < 1e-9

    def test_weights_sum_to_one(self) -> None:
        assert abs(sum(REWARD_WEIGHTS.values()) - 1.0) < 1e-9


class TestComputeDrift:
    def test_identical_returns_zero(self) -> None:
        original = _make_design_point()
        candidate = _make_candidate()
        assert compute_drift(candidate, original) == 0.0

    def test_one_field_changed(self) -> None:
        original = _make_design_point()
        candidate = _make_candidate(customer="Veterinarians")
        drift = compute_drift(candidate, original)
        assert abs(drift - 1.0 / 7.0) < 1e-9

    def test_all_fields_changed(self) -> None:
        original = _make_design_point()
        candidate = _make_candidate(
            customer="Vets",
            problem="Different",
            solution="Different",
            value_prop="Different",
            wedge="Different",
            business_model="Different",
            gtm_path="Different",
        )
        assert compute_drift(candidate, original) == 1.0

    def test_three_fields_changed(self) -> None:
        original = _make_design_point()
        candidate = _make_candidate(
            customer="Vets",
            problem="Different",
            solution="Different",
        )
        drift = compute_drift(candidate, original)
        assert abs(drift - 3.0 / 7.0) < 1e-9


class TestComputeComplexity:
    def test_short_fields_low_complexity(self) -> None:
        candidate = _make_candidate()
        complexity = compute_complexity(candidate)
        assert 0.0 <= complexity <= 1.0
        assert complexity < 0.5

    def test_long_fields_high_complexity(self) -> None:
        candidate = _make_candidate(
            customer="x" * 300,
            problem="x" * 300,
            solution="x" * 300,
            value_prop="x" * 300,
            wedge="x" * 300,
            business_model="x" * 300,
            gtm_path="x" * 300,
        )
        assert compute_complexity(candidate) == 1.0

    def test_boundary_at_200_chars(self) -> None:
        candidate = _make_candidate(
            customer="x" * 200,
            problem="x" * 200,
            solution="x" * 200,
            value_prop="x" * 200,
            wedge="x" * 200,
            business_model="x" * 200,
            gtm_path="x" * 200,
        )
        assert abs(compute_complexity(candidate) - 1.0) < 1e-9


class TestScoreCandidate:
    def test_score_with_no_drift(self) -> None:
        original = _make_design_point()
        candidate = _make_candidate()
        es = _make_eval_scores()
        config = RunConfig()

        sc = score_candidate(candidate, es, original, config)

        assert sc.drift_score == 0.0
        assert sc.composite_score == compute_reward(es)
        assert sc.final_score > 0.0

    def test_drift_penalty_reduces_score(self) -> None:
        original = _make_design_point()
        candidate_same = _make_candidate()
        candidate_diff = _make_candidate(customer="Vets", problem="Different", solution="Different")
        es = _make_eval_scores()
        config = RunConfig()

        sc_same = score_candidate(candidate_same, es, original, config)
        sc_diff = score_candidate(candidate_diff, es, original, config)

        assert sc_same.final_score > sc_diff.final_score

    def test_high_drift_weight_amplifies_penalty(self) -> None:
        original = _make_design_point()
        candidate = _make_candidate(customer="Vets")
        es = _make_eval_scores()
        config_low = RunConfig(drift_weight=0.1)
        config_high = RunConfig(drift_weight=0.5)

        sc_low = score_candidate(candidate, es, original, config_low)
        sc_high = score_candidate(candidate, es, original, config_high)

        assert sc_low.final_score > sc_high.final_score

    def test_formula_correctness(self) -> None:
        original = _make_design_point()
        candidate = _make_candidate(customer="Vets")
        es = _make_eval_scores(pain=8.0, specificity=7.0, differentiation=6.0,
                               testability=9.0, feasibility=7.5)
        config = RunConfig(drift_weight=0.15, complexity_weight=0.1)

        sc = score_candidate(candidate, es, original, config)

        reward = compute_reward(es)
        drift = compute_drift(candidate, original)
        complexity = compute_complexity(candidate)
        expected_final = reward - 0.15 * drift * 10.0 - 0.1 * complexity * 10.0

        assert abs(sc.final_score - expected_final) < 1e-9
        assert abs(sc.composite_score - reward) < 1e-9


class TestSelectTopK:
    def _make_scored(self, final_score: float, summary: str = "c") -> ScoredCandidate:
        return ScoredCandidate(
            candidate=_make_candidate(summary=summary),
            eval_scores=_make_eval_scores(),
            composite_score=7.0,
            drift_score=0.0,
            complexity_score=0.0,
            final_score=final_score,
        )

    def test_selects_highest(self) -> None:
        candidates = [
            self._make_scored(5.0, "low"),
            self._make_scored(9.0, "high"),
            self._make_scored(7.0, "mid"),
        ]
        top = select_top_k(candidates, k=2)
        assert len(top) == 2
        assert top[0].final_score == 9.0
        assert top[1].final_score == 7.0

    def test_k_larger_than_list(self) -> None:
        candidates = [self._make_scored(5.0)]
        top = select_top_k(candidates, k=3)
        assert len(top) == 1

    def test_empty_list(self) -> None:
        top = select_top_k([], k=2)
        assert top == []

    def test_k_zero(self) -> None:
        candidates = [self._make_scored(5.0)]
        top = select_top_k(candidates, k=0)
        assert top == []
