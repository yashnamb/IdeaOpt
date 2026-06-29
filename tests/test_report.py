"""Tests for the markdown report generator."""

from __future__ import annotations

from ideaopt.models import (
    BudgetSummary,
    CandidateHypothesis,
    DesignPoint,
    EvalScore,
    ExplorationReport,
    IterationResult,
    ScoredCandidate,
)
from ideaopt.report import generate_report


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
        rationale="High pain, clear ROI, testable in 1 week",
        iteration=iteration,
    )
    eval_scores = EvalScore(
        pain=pain,
        specificity=7.0,
        differentiation=6.0,
        testability=8.0,
        feasibility=7.0,
        rationale="Strong pain point with clear testability",
    )
    return ScoredCandidate(
        candidate=candidate,
        eval_scores=eval_scores,
        composite_score=score + 0.3,
        drift_score=0.1,
        complexity_score=0.2,
        final_score=score,
    )


def _make_report(
    num_iterations: int = 1,
    num_candidates: int = 2,
) -> ExplorationReport:
    dp = _make_design_point()
    iterations: list[IterationResult] = []

    for i in range(1, num_iterations + 1):
        candidates = []
        scored_candidates = []
        for j in range(num_candidates):
            sc = _make_scored(
                summary=f"Candidate {j + 1} iteration {i}",
                score=7.0 - j * 0.5,
                pain=8.0 - j,
                iteration=i,
            )
            candidates.append(sc.candidate)
            scored_candidates.append(sc)

        merged = None
        if num_candidates >= 2:
            merged = CandidateHypothesis(
                design_point=dp,
                summary=f"Merged hypothesis iteration {i}",
                rationale="Combined best elements from top candidates",
                iteration=i,
            )

        iterations.append(IterationResult(
            iteration=i,
            candidates=candidates,
            scored_candidates=scored_candidates,
            merged_candidate=merged,
        ))

    best = _make_scored(summary="Best overall hypothesis", score=8.5, pain=9.0)
    budget = BudgetSummary(
        total_calls=15,
        successful_calls=13,
        failed_calls=2,
        total_duration=92.3,
    )

    return ExplorationReport(
        original_idea="AI tool for dental clinics to handle phone calls",
        design_point=dp,
        iterations=iterations,
        best_candidate=best,
        validation_experiment="Interview 10 solo dental practices about call handling pain",
        budget_summary=budget,
    )


class TestGenerateReport:
    def test_has_all_13_sections(self) -> None:
        report = _make_report()
        markdown = generate_report(report)
        required_headers = [
            "## 1. Original Founder Idea",
            "## 2. Extracted Design Dimensions",
            "## 3. Candidate Hypotheses Generated",
            "## 4. Evaluation Score Table",
            "## 5. Top Candidates by Iteration",
            "## 6. Merged/Refined Hypotheses",
            "## 7. Final Selected Startup Hypothesis",
            "## 8. Why This Hypothesis Won",
            "## 9. What Was Rejected and Why",
            "## 10. Riskiest Remaining Assumption",
            "## 11. First Validation Experiment",
            "## 12. Decision Rule",
            "## 13. Recommended 7-Day Customer Discovery Plan",
        ]
        for header in required_headers:
            assert header in markdown, f"Missing section: {header}"

    def test_contains_original_idea(self) -> None:
        report = _make_report()
        markdown = generate_report(report)
        assert "AI tool for dental clinics to handle phone calls" in markdown

    def test_contains_design_dimensions(self) -> None:
        report = _make_report()
        markdown = generate_report(report)
        assert "Solo dental practices" in markdown
        assert "Missed phone calls losing new patients" in markdown
        assert "AI receptionist that answers and books" in markdown

    def test_contains_scores(self) -> None:
        report = _make_report()
        markdown = generate_report(report)
        assert "8.5" in markdown

    def test_contains_budget_summary(self) -> None:
        report = _make_report()
        markdown = generate_report(report)
        assert "15" in markdown
        assert "13" in markdown
        assert "92.3" in markdown

    def test_contains_validation_experiment(self) -> None:
        report = _make_report()
        markdown = generate_report(report)
        assert "Interview 10 solo dental practices" in markdown

    def test_contains_candidate_summaries(self) -> None:
        report = _make_report()
        markdown = generate_report(report)
        assert "Candidate 1 iteration 1" in markdown
        assert "Candidate 2 iteration 1" in markdown

    def test_contains_merged_hypothesis(self) -> None:
        report = _make_report()
        markdown = generate_report(report)
        assert "Merged hypothesis iteration 1" in markdown

    def test_contains_decision_rule(self) -> None:
        report = _make_report()
        markdown = generate_report(report)
        assert "CONTINUE" in markdown
        assert "PIVOT" in markdown
        assert "KILL" in markdown

    def test_contains_7_day_plan(self) -> None:
        report = _make_report()
        markdown = generate_report(report)
        assert "Day 1-2" in markdown
        assert "Day 3-5" in markdown
        assert "Day 6-7" in markdown

    def test_report_title(self) -> None:
        report = _make_report()
        markdown = generate_report(report)
        assert "# Startup Hypothesis Design Space Report" in markdown


class TestReportEdgeCases:
    def test_empty_iterations(self) -> None:
        dp = _make_design_point()
        best = _make_scored()
        report = ExplorationReport(
            original_idea="Test idea",
            design_point=dp,
            iterations=[],
            best_candidate=best,
            validation_experiment="Test experiment",
            budget_summary=BudgetSummary(
                total_calls=1,
                successful_calls=1,
                failed_calls=0,
                total_duration=5.0,
            ),
        )
        markdown = generate_report(report)
        assert "## 1. Original Founder Idea" in markdown
        assert "## 7. Final Selected Startup Hypothesis" in markdown

    def test_single_candidate(self) -> None:
        report = _make_report(num_candidates=1)
        markdown = generate_report(report)
        assert "## 4. Evaluation Score Table" in markdown

    def test_multiple_iterations(self) -> None:
        report = _make_report(num_iterations=3)
        markdown = generate_report(report)
        assert "Iteration 1" in markdown
        assert "Iteration 2" in markdown
        assert "Iteration 3" in markdown

    def test_no_merged_candidate(self) -> None:
        dp = _make_design_point()
        sc = _make_scored()
        iteration = IterationResult(
            iteration=1,
            candidates=[sc.candidate],
            scored_candidates=[sc],
            merged_candidate=None,
        )
        report = ExplorationReport(
            original_idea="Test",
            design_point=dp,
            iterations=[iteration],
            best_candidate=sc,
            validation_experiment="Test",
            budget_summary=BudgetSummary(
                total_calls=1, successful_calls=1,
                failed_calls=0, total_duration=1.0,
            ),
        )
        markdown = generate_report(report)
        assert "No merge performed" in markdown
