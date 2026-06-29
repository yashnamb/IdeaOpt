"""Tests for ideaopt domain models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ideaopt.models import (
    BudgetSummary,
    CandidateHypothesis,
    DesignPoint,
    EvalScore,
    ExplorationReport,
    IterationResult,
    RunConfig,
    ScoredCandidate,
)


def _make_design_point(**overrides: str) -> DesignPoint:
    defaults = {
        "customer": "Solo dentists in US suburbs",
        "problem": "Missed calls during procedures lose new patients",
        "solution": "AI receptionist that answers, books, and follows up",
        "value_prop": "Never miss a new patient call again",
        "wedge": "After-hours call handling for solo practices",
        "business_model": "$299/mo per practice",
        "gtm_path": "Direct outreach to solo dentists via dental forums",
    }
    defaults.update(overrides)
    return DesignPoint(**defaults)


def _make_candidate(iteration: int = 0, **dp_overrides: str) -> CandidateHypothesis:
    return CandidateHypothesis(
        design_point=_make_design_point(**dp_overrides),
        summary="AI receptionist for solo dentists",
        rationale="High pain, clear wedge, testable in 1 week",
        iteration=iteration,
    )


def _make_eval_scores(**overrides: float) -> EvalScore:
    defaults: dict[str, float | str] = {
        "pain": 8.0,
        "specificity": 7.0,
        "differentiation": 6.0,
        "testability": 9.0,
        "feasibility": 7.5,
        "rationale": "Strong pain point with clear customer segment",
    }
    defaults.update(overrides)
    return EvalScore(**defaults)  # type: ignore[arg-type]


class TestDesignPoint:
    def test_construction(self) -> None:
        dp = _make_design_point()
        assert dp.customer == "Solo dentists in US suburbs"
        assert dp.wedge == "After-hours call handling for solo practices"

    def test_strict_mode_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError, match="extra_forbidden"):
            _make_design_point(extra_field="not allowed")  # type: ignore[arg-type]

    def test_serialization_roundtrip(self) -> None:
        dp = _make_design_point()
        data = dp.model_dump()
        restored = DesignPoint(**data)
        assert restored == dp

    def test_json_roundtrip(self) -> None:
        dp = _make_design_point()
        json_str = dp.model_dump_json()
        restored = DesignPoint.model_validate_json(json_str)
        assert restored == dp

    def test_strict_mode_rejects_wrong_types(self) -> None:
        with pytest.raises(ValidationError):
            DesignPoint(
                customer=123,  # type: ignore[arg-type]
                problem="x",
                solution="x",
                value_prop="x",
                wedge="x",
                business_model="x",
                gtm_path="x",
            )


class TestCandidateHypothesis:
    def test_construction(self) -> None:
        c = _make_candidate(iteration=1)
        assert c.iteration == 1
        assert c.design_point.customer == "Solo dentists in US suburbs"

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError, match="extra_forbidden"):
            CandidateHypothesis(
                design_point=_make_design_point(),
                summary="test",
                rationale="test",
                iteration=0,
                extra="nope",  # type: ignore[call-arg]
            )


class TestEvalScore:
    def test_construction(self) -> None:
        es = _make_eval_scores()
        assert es.pain == 8.0
        assert es.feasibility == 7.5

    def test_bounds_enforcement(self) -> None:
        with pytest.raises(ValidationError):
            _make_eval_scores(pain=11.0)

    def test_lower_bound(self) -> None:
        with pytest.raises(ValidationError):
            _make_eval_scores(testability=-1.0)

    def test_zero_scores_valid(self) -> None:
        es = _make_eval_scores(pain=0.0, specificity=0.0, differentiation=0.0)
        assert es.pain == 0.0

    def test_max_scores_valid(self) -> None:
        es = _make_eval_scores(pain=10.0, specificity=10.0)
        assert es.pain == 10.0


class TestScoredCandidate:
    def test_construction(self) -> None:
        sc = ScoredCandidate(
            candidate=_make_candidate(),
            eval_scores=_make_eval_scores(),
            composite_score=7.5,
            drift_score=0.2,
            complexity_score=0.3,
            final_score=6.8,
        )
        assert sc.final_score == 6.8
        assert sc.candidate.summary == "AI receptionist for solo dentists"


class TestRunConfig:
    def test_defaults(self) -> None:
        config = RunConfig()
        assert config.max_iterations == 2
        assert config.candidates_per_round == 5
        assert config.top_k == 2
        assert config.max_agent_calls == 30
        assert config.agent_timeout == 300
        assert config.drift_weight == 0.15
        assert config.complexity_weight == 0.1

    def test_custom_values(self) -> None:
        config = RunConfig(max_iterations=5, top_k=3, drift_weight=0.3)
        assert config.max_iterations == 5
        assert config.top_k == 3
        assert config.drift_weight == 0.3


class TestIterationResult:
    def test_construction_with_merged(self) -> None:
        c = _make_candidate()
        sc = ScoredCandidate(
            candidate=c,
            eval_scores=_make_eval_scores(),
            composite_score=7.0,
            drift_score=0.0,
            complexity_score=0.2,
            final_score=6.8,
        )
        ir = IterationResult(
            iteration=0,
            candidates=[c],
            scored_candidates=[sc],
            merged_candidate=c,
        )
        assert ir.iteration == 0
        assert len(ir.scored_candidates) == 1

    def test_construction_without_merged(self) -> None:
        ir = IterationResult(
            iteration=0,
            candidates=[],
            scored_candidates=[],
            merged_candidate=None,
        )
        assert ir.merged_candidate is None


class TestExplorationReport:
    def test_construction(self) -> None:
        c = _make_candidate()
        es = _make_eval_scores()
        sc = ScoredCandidate(
            candidate=c,
            eval_scores=es,
            composite_score=7.0,
            drift_score=0.0,
            complexity_score=0.2,
            final_score=6.8,
        )
        report = ExplorationReport(
            original_idea="AI receptionist for dentists",
            design_point=_make_design_point(),
            iterations=[],
            best_candidate=sc,
            validation_experiment="Cold-call 10 solo dentists",
            budget_summary=BudgetSummary(
                total_calls=15,
                successful_calls=14,
                failed_calls=1,
                total_duration=120.5,
            ),
        )
        assert report.original_idea == "AI receptionist for dentists"
        assert report.budget_summary.total_calls == 15


class TestBudgetSummary:
    def test_construction(self) -> None:
        bs = BudgetSummary(
            total_calls=10,
            successful_calls=9,
            failed_calls=1,
            total_duration=85.3,
        )
        assert bs.total_calls == 10
        assert bs.total_duration == 85.3

    def test_serialization(self) -> None:
        bs = BudgetSummary(
            total_calls=5,
            successful_calls=5,
            failed_calls=0,
            total_duration=42.0,
        )
        data = bs.model_dump()
        restored = BudgetSummary(**data)
        assert restored == bs
