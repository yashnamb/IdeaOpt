"""Tests for the live HTML visualizer."""

from __future__ import annotations

import json

from ideaopt.models import (
    BudgetSummary,
    CandidateHypothesis,
    DesignPoint,
    EvalScore,
    IterationResult,
    ReportState,
    ScoredCandidate,
)
from ideaopt.visualizer import generate_html


def _make_design_point(**overrides: str) -> DesignPoint:
    defaults = {
        "customer": "Solo dental practices",
        "problem": "Missed phone calls losing new patients",
        "solution": "AI receptionist that answers and books",
        "value_prop": "Never miss a new patient call",
        "wedge": "After-hours call handling",
        "business_model": "Monthly SaaS at $299/mo",
        "gtm_path": "Direct outreach via dental forums",
    }
    defaults.update(overrides)
    return DesignPoint(**defaults)


def _make_scored(
    summary: str = "AI receptionist for dentists",
    score: float = 7.0,
    pain: float = 8.0,
    iteration: int = 1,
    **dp_overrides: str,
) -> ScoredCandidate:
    dp = _make_design_point(**dp_overrides)
    candidate = CandidateHypothesis(
        design_point=dp,
        summary=summary,
        rationale="High pain, clear ROI",
        iteration=iteration,
    )
    eval_scores = EvalScore(
        pain=pain,
        specificity=7.0,
        differentiation=6.0,
        testability=8.0,
        feasibility=7.0,
        rationale="Strong pain point",
    )
    return ScoredCandidate(
        candidate=candidate,
        eval_scores=eval_scores,
        composite_score=score + 0.3,
        drift_score=0.1,
        complexity_score=0.2,
        final_score=score,
    )


def _make_encoding_state() -> ReportState:
    return ReportState(
        status="encoding",
        original_idea="AI tool for dental clinics",
    )


def _make_complete_state() -> ReportState:
    dp = _make_design_point()
    sc1 = _make_scored(summary="Candidate 1", score=7.5, pain=8.0)
    sc2 = _make_scored(summary="Candidate 2", score=6.0, pain=6.0)
    merged = CandidateHypothesis(
        design_point=dp,
        summary="Merged hypothesis",
        rationale="Combined best elements",
        iteration=1,
    )
    iteration = IterationResult(
        iteration=1,
        candidates=[sc1.candidate, sc2.candidate],
        scored_candidates=[sc1, sc2],
        merged_candidate=merged,
    )
    return ReportState(
        status="complete",
        original_idea="AI tool for dental clinics",
        design_point=dp,
        iterations=[iteration],
        current_iteration=1,
        current_candidates=[sc1.candidate, sc2.candidate],
        current_scored=[sc1, sc2],
        best_candidate=sc1,
        validation_experiment="Interview 10 solo dental practices",
        budget_summary=BudgetSummary(
            total_calls=15,
            successful_calls=13,
            failed_calls=2,
            total_duration=92.3,
        ),
    )


class TestVisualizerHTML:
    def test_html_valid_at_encoding_status(self) -> None:
        state = _make_encoding_state()
        html = generate_html(state)
        assert "<!DOCTYPE html>" in html
        assert "<title>IdeaOpt Report</title>" in html
        assert '<meta http-equiv="refresh" content="3">' in html

    def test_html_valid_at_complete_status(self) -> None:
        state = _make_complete_state()
        html = generate_html(state)
        assert "<!DOCTYPE html>" in html
        assert '<meta http-equiv="refresh"' not in html

    def test_json_embedded(self) -> None:
        state = _make_complete_state()
        html = generate_html(state)
        assert "var STATE =" in html
        start = html.index("var STATE = ") + len("var STATE = ")
        end = html.index(";", start)
        embedded = html[start:end]
        parsed = json.loads(embedded)
        assert parsed["status"] == "complete"
        assert parsed["original_idea"] == "AI tool for dental clinics"

    def test_html_escapes_script_tags(self) -> None:
        state = ReportState(
            status="encoding",
            original_idea='My idea </script><script>alert("xss")</script>',
        )
        html = generate_html(state)
        assert "</script><script>" not in html
        assert r"<\/script>" in html

    def test_all_sections_present(self) -> None:
        state = _make_complete_state()
        html = generate_html(state)
        assert "section-design-point" in html
        assert "section-timeline" in html
        assert "section-radar" in html
        assert "section-progression" in html
        assert "section-evolution" in html
        assert "section-results" in html
        assert "IdeaOpt Design Space Report" in html

    def test_chart_js_included(self) -> None:
        state = _make_encoding_state()
        html = generate_html(state)
        assert "https://cdn.jsdelivr.net/npm/chart.js@4" in html

    def test_placeholder_sections(self) -> None:
        state = _make_encoding_state()
        html = generate_html(state)
        assert "Waiting for data..." in html
