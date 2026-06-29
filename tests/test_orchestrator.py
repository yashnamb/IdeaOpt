"""Tests for the orchestrator exploration loop with mocked agent runner."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from ideaopt.agents.runner import AgentError
from ideaopt.models import (
    BudgetSummary,
    CandidateHypothesis,
    DesignPoint,
    EvalScore,
    ExplorationReport,
    RunConfig,
    ScoredCandidate,
)
from ideaopt.orchestrator import (
    _check_stop_conditions,
    _merge_eval_scores,
    _parse_candidates,
    _parse_model,
    run_exploration,
)

IDEA = "AI receptionist for dental clinics"

DESIGN_POINT_JSON = json.dumps({
    "customer": "dental clinics",
    "problem": "missed calls",
    "solution": "AI receptionist",
    "value_prop": "recover lost revenue",
    "wedge": "after-hours calls",
    "business_model": "SaaS subscription",
    "gtm_path": "direct outreach",
})

DESIGN_POINT = DesignPoint(
    customer="dental clinics",
    problem="missed calls",
    solution="AI receptionist",
    value_prop="recover lost revenue",
    wedge="after-hours calls",
    business_model="SaaS subscription",
    gtm_path="direct outreach",
)


def _make_candidate(summary: str, iteration: int = 1) -> dict[str, object]:
    return {
        "design_point": DESIGN_POINT.model_dump(),
        "summary": summary,
        "rationale": f"Testing {summary}",
        "iteration": iteration,
    }


def _make_eval(
    pain: float = 7.0,
    specificity: float = 7.0,
    differentiation: float = 6.0,
    testability: float = 7.0,
    feasibility: float = 8.0,
) -> dict[str, object]:
    return {
        "pain": pain,
        "specificity": specificity,
        "differentiation": differentiation,
        "testability": testability,
        "feasibility": feasibility,
        "rationale": "Good candidate for testing.",
    }


CANDIDATES_JSON = json.dumps([
    _make_candidate("Missed-call recovery"),
    _make_candidate("After-hours triage"),
])

EVAL_HIGH = json.dumps(_make_eval(pain=8.0, specificity=8.0, differentiation=7.0))
EVAL_MED = json.dumps(_make_eval(pain=6.0, specificity=6.0, differentiation=5.0))
EVAL_LOW = json.dumps(_make_eval(pain=4.0, specificity=4.0, differentiation=3.0))

MERGED_JSON = json.dumps(_make_candidate("Merged: missed-call + triage"))


def _mock_run_agent_factory(
    responses: dict[str, str | Exception] | None = None,
) -> AsyncMock:
    """Create a mock run_agent that returns role-specific responses."""
    default_responses: dict[str, str] = {
        "encoder": DESIGN_POINT_JSON,
        "generator": CANDIDATES_JSON,
        "validator": EVAL_HIGH,
        "competitor": EVAL_MED,
        "customer_discovery": EVAL_MED,
        "merger": MERGED_JSON,
    }
    if responses:
        for k, v in responses.items():
            default_responses[k] = v  # type: ignore[assignment]

    call_log: list[dict[str, str]] = []

    async def mock_run_agent(
        role: str,
        task: str,
        cwd: object,
        *,
        model: str | None = None,
        timeout: int = 300,
    ) -> str:
        call_log.append({"role": role, "task": task if isinstance(task, str) else str(task)})
        resp = default_responses.get(role)
        if resp is None:
            raise AgentError(f"No mock response for role: {role}")
        if isinstance(resp, Exception):
            raise resp
        return resp

    mock = AsyncMock(side_effect=mock_run_agent)
    mock.call_log = call_log  # type: ignore[attr-defined]
    return mock


@pytest.fixture()
def small_config() -> RunConfig:
    return RunConfig(
        max_iterations=2,
        candidates_per_round=2,
        top_k=2,
        max_agent_calls=50,
        agent_timeout=10,
    )


class TestFullLoop:
    async def test_returns_exploration_report(self, small_config: RunConfig) -> None:
        mock = _mock_run_agent_factory()
        with patch("ideaopt.orchestrator.run_agent", mock):
            report = await run_exploration(IDEA, small_config)

        assert isinstance(report, ExplorationReport)
        assert report.original_idea == IDEA
        assert report.design_point == DESIGN_POINT
        assert len(report.iterations) >= 1
        assert isinstance(report.best_candidate, ScoredCandidate)
        assert isinstance(report.budget_summary, BudgetSummary)

    async def test_iterations_contain_candidates_and_scores(
        self, small_config: RunConfig,
    ) -> None:
        mock = _mock_run_agent_factory()
        with patch("ideaopt.orchestrator.run_agent", mock):
            report = await run_exploration(IDEA, small_config)

        for it_result in report.iterations:
            assert len(it_result.candidates) > 0
            assert len(it_result.scored_candidates) > 0

    async def test_best_candidate_has_positive_score(
        self, small_config: RunConfig,
    ) -> None:
        mock = _mock_run_agent_factory()
        with patch("ideaopt.orchestrator.run_agent", mock):
            report = await run_exploration(IDEA, small_config)

        assert report.best_candidate.final_score > 0


class TestOriginalIdeaPassthrough:
    async def test_original_idea_in_every_agent_call(
        self, small_config: RunConfig,
    ) -> None:
        small_config = RunConfig(
            max_iterations=1,
            candidates_per_round=2,
            top_k=2,
            max_agent_calls=50,
            agent_timeout=10,
        )
        mock = _mock_run_agent_factory()
        with patch("ideaopt.orchestrator.run_agent", mock):
            await run_exploration(IDEA, small_config)

        for call_info in mock.call_log:  # type: ignore[attr-defined]
            role = call_info["role"]
            task_str = call_info["task"]
            if role == "encoder":
                assert IDEA in task_str
            else:
                parsed = json.loads(task_str)
                assert "original_idea" in parsed, (
                    f"original_idea missing from {role} task"
                )
                assert parsed["original_idea"] == IDEA


class TestStopConditions:
    async def test_stops_at_max_iterations(self) -> None:
        config = RunConfig(
            max_iterations=1,
            candidates_per_round=2,
            top_k=2,
            max_agent_calls=100,
            agent_timeout=10,
        )
        mock = _mock_run_agent_factory()
        with patch("ideaopt.orchestrator.run_agent", mock):
            report = await run_exploration(IDEA, config)

        assert len(report.iterations) == 1

    async def test_stops_at_budget_exhaustion(self) -> None:
        config = RunConfig(
            max_iterations=10,
            candidates_per_round=2,
            top_k=2,
            max_agent_calls=5,
            agent_timeout=10,
        )
        mock = _mock_run_agent_factory()
        with patch("ideaopt.orchestrator.run_agent", mock):
            report = await run_exploration(IDEA, config)

        assert report.budget_summary.total_calls <= config.max_agent_calls + 3

    async def test_stops_on_score_plateau(self) -> None:
        config = RunConfig(
            max_iterations=5,
            candidates_per_round=2,
            top_k=2,
            max_agent_calls=100,
            agent_timeout=10,
        )
        mock = _mock_run_agent_factory()
        with patch("ideaopt.orchestrator.run_agent", mock):
            report = await run_exploration(IDEA, config)

        assert len(report.iterations) <= config.max_iterations


class TestEvaluatorFailure:
    async def test_graceful_degradation_one_evaluator_fails(
        self, small_config: RunConfig,
    ) -> None:
        responses = {
            "validator": AgentError("validator timeout"),
        }
        mock = _mock_run_agent_factory(responses)  # type: ignore[arg-type]
        with patch("ideaopt.orchestrator.run_agent", mock):
            report = await run_exploration(IDEA, small_config)

        assert isinstance(report, ExplorationReport)
        assert len(report.iterations) >= 1
        assert report.best_candidate.final_score > 0

    async def test_graceful_degradation_two_evaluators_fail(
        self, small_config: RunConfig,
    ) -> None:
        responses = {
            "validator": AgentError("fail"),
            "competitor": AgentError("fail"),
        }
        mock = _mock_run_agent_factory(responses)  # type: ignore[arg-type]
        with patch("ideaopt.orchestrator.run_agent", mock):
            report = await run_exploration(IDEA, small_config)

        assert isinstance(report, ExplorationReport)
        assert len(report.iterations) >= 1

    async def test_all_evaluators_fail_skips_candidate(
        self, small_config: RunConfig,
    ) -> None:
        responses = {
            "validator": AgentError("fail"),
            "competitor": AgentError("fail"),
            "customer_discovery": AgentError("fail"),
        }
        mock = _mock_run_agent_factory(responses)  # type: ignore[arg-type]
        with patch("ideaopt.orchestrator.run_agent", mock):
            report = await run_exploration(IDEA, small_config)

        assert isinstance(report, ExplorationReport)


class TestMergerFailure:
    async def test_continues_without_merged_candidate(
        self, small_config: RunConfig,
    ) -> None:
        responses = {"merger": AgentError("merger failed")}
        mock = _mock_run_agent_factory(responses)  # type: ignore[arg-type]
        with patch("ideaopt.orchestrator.run_agent", mock):
            report = await run_exploration(IDEA, small_config)

        assert isinstance(report, ExplorationReport)
        for it_result in report.iterations:
            assert it_result.merged_candidate is None


class TestReportPath:
    async def test_report_path_writes_html(
        self, small_config: RunConfig, tmp_path: Path,
    ) -> None:
        report_html = tmp_path / "report.html"
        mock = _mock_run_agent_factory()
        with patch("ideaopt.orchestrator.run_agent", mock):
            await run_exploration(IDEA, small_config, report_path=report_html)

        assert report_html.exists()
        content = report_html.read_text()
        assert "<!DOCTYPE html" in content
        assert "complete" in content


class TestCheckStopConditions:
    def _make_scored(self, score: float, summary: str = "test") -> ScoredCandidate:
        candidate = CandidateHypothesis(
            design_point=DESIGN_POINT,
            summary=summary,
            rationale="test",
            iteration=1,
        )
        eval_scores = EvalScore(
            pain=7.0, specificity=7.0, differentiation=6.0,
            testability=7.0, feasibility=8.0, rationale="test",
        )
        return ScoredCandidate(
            candidate=candidate,
            eval_scores=eval_scores,
            composite_score=score,
            drift_score=0.0,
            complexity_score=0.0,
            final_score=score,
        )

    def test_no_stop_first_iteration(self) -> None:
        best = self._make_scored(7.0)
        from ideaopt.budget import BudgetTracker
        budget = BudgetTracker(max_iterations=5, max_agent_calls=100)
        result = _check_stop_conditions(best, None, None, 0, budget)
        assert result is None

    def test_stops_on_plateau(self) -> None:
        best = self._make_scored(7.2)
        from ideaopt.budget import BudgetTracker
        budget = BudgetTracker(max_iterations=5, max_agent_calls=100)
        result = _check_stop_conditions(best, "other", 7.0, 0, budget)
        assert result is not None
        assert "plateau" in result

    def test_stops_on_stagnation(self) -> None:
        best = self._make_scored(8.0)
        from ideaopt.budget import BudgetTracker
        budget = BudgetTracker(max_iterations=5, max_agent_calls=100)
        result = _check_stop_conditions(best, "test", 5.0, 1, budget)
        assert result is not None
        assert "consecutive" in result

    def test_no_stop_with_improvement(self) -> None:
        best = self._make_scored(8.0)
        from ideaopt.budget import BudgetTracker
        budget = BudgetTracker(max_iterations=5, max_agent_calls=100)
        result = _check_stop_conditions(best, "other", 7.0, 0, budget)
        assert result is None


class TestMergeEvalScores:
    def test_averages_scores(self) -> None:
        scores = [
            EvalScore(pain=8.0, specificity=6.0, differentiation=7.0,
                      testability=5.0, feasibility=9.0, rationale="A"),
            EvalScore(pain=6.0, specificity=8.0, differentiation=5.0,
                      testability=7.0, feasibility=7.0, rationale="B"),
        ]
        merged = _merge_eval_scores(scores)
        assert merged.pain == 7.0
        assert merged.specificity == 7.0
        assert merged.differentiation == 6.0
        assert merged.testability == 6.0
        assert merged.feasibility == 8.0
        assert "A" in merged.rationale
        assert "B" in merged.rationale

    def test_single_score_passthrough(self) -> None:
        score = EvalScore(pain=8.0, specificity=6.0, differentiation=7.0,
                          testability=5.0, feasibility=9.0, rationale="Only one")
        merged = _merge_eval_scores([score])
        assert merged.pain == 8.0
        assert merged.rationale == "Only one"


class TestParseModel:
    def test_parses_valid_json(self) -> None:
        result = _parse_model(DESIGN_POINT_JSON, DesignPoint)
        assert result == DESIGN_POINT

    def test_rejects_invalid_json(self) -> None:
        with pytest.raises(ValueError, match="Cannot parse JSON"):
            _parse_model("not json at all", DesignPoint)

    def test_rejects_wrong_schema(self) -> None:
        with pytest.raises(ValueError, match="Validation failed"):
            _parse_model('{"wrong": "schema"}', DesignPoint)

    def test_extracts_from_markdown_fences(self) -> None:
        wrapped = f"Here is the result:\n```json\n{DESIGN_POINT_JSON}\n```"
        result = _parse_model(wrapped, DesignPoint)
        assert result == DESIGN_POINT


class TestParseCandidates:
    def test_parses_array(self) -> None:
        candidates = _parse_candidates(CANDIDATES_JSON, 1)
        assert len(candidates) == 2
        assert candidates[0].summary == "Missed-call recovery"

    def test_parses_wrapped_object(self) -> None:
        wrapped = json.dumps({"candidates": [_make_candidate("Test")]})
        candidates = _parse_candidates(wrapped, 1)
        assert len(candidates) == 1

    def test_injects_iteration(self) -> None:
        raw = json.dumps([{
            "design_point": DESIGN_POINT.model_dump(),
            "summary": "No iteration field",
            "rationale": "Test",
        }])
        candidates = _parse_candidates(raw, 3)
        assert candidates[0].iteration == 3

    def test_skips_invalid_candidates(self) -> None:
        raw = json.dumps([
            _make_candidate("Valid"),
            {"invalid": "candidate"},
        ])
        candidates = _parse_candidates(raw, 1)
        assert len(candidates) == 1
