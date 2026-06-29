"""Markdown report generator for exploration results."""

from __future__ import annotations

from ideaopt.models import (
    ExplorationReport,
    ScoredCandidate,
)

_DIMENSION_LABELS = [
    ("customer", "Customer"),
    ("problem", "Problem"),
    ("solution", "Solution"),
    ("value_prop", "Value Prop"),
    ("wedge", "Wedge"),
    ("business_model", "Business Model"),
    ("gtm_path", "GTM Path"),
]

_SCORE_FIELDS = ["pain", "specificity", "differentiation", "testability", "feasibility"]


def generate_report(report: ExplorationReport) -> str:
    """Generate the full 13-section markdown report from exploration data."""
    sections = [
        "# Startup Hypothesis Design Space Report",
        _section_1(report),
        _section_2(report),
        _section_3(report),
        _section_4(report),
        _section_5(report),
        _section_6(report),
        _section_7(report),
        _section_8(report),
        _section_9(report),
        _section_10(report),
        _section_11(report),
        _section_12(report),
        _section_13(report),
        _budget_appendix(report),
    ]
    return "\n\n".join(sections) + "\n"


def _section_1(report: ExplorationReport) -> str:
    return f"## 1. Original Founder Idea\n\n> {report.original_idea}"


def _section_2(report: ExplorationReport) -> str:
    dp = report.design_point
    rows = "\n".join(
        f"| {label} | {getattr(dp, field)} |"
        for field, label in _DIMENSION_LABELS
    )
    return f"## 2. Extracted Design Dimensions\n\n| Dimension | Value |\n|---|---|\n{rows}"


def _section_3(report: ExplorationReport) -> str:
    lines = ["## 3. Candidate Hypotheses Generated"]
    for it in report.iterations:
        lines.append(f"\n### Iteration {it.iteration}")
        for i, c in enumerate(it.candidates, 1):
            lines.append(f"\n**Candidate {i}:** {c.summary}")
            lines.append(f"- Rationale: {c.rationale}")
    if not report.iterations:
        lines.append("\nNo candidates were generated.")
    return "\n".join(lines)


def _section_4(report: ExplorationReport) -> str:
    all_scored = _collect_scored(report)
    lines = [
        "## 4. Evaluation Score Table",
        "",
        "| Candidate | Pain | Spec. | Diff. | Test. | Feas. | Drift | Final |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for sc in all_scored:
        e = sc.eval_scores
        lines.append(
            f"| {_truncate(sc.candidate.summary, 50)} "
            f"| {e.pain:.1f} | {e.specificity:.1f} | {e.differentiation:.1f} "
            f"| {e.testability:.1f} | {e.feasibility:.1f} "
            f"| {sc.drift_score:.2f} | {sc.final_score:.2f} |"
        )
    if not all_scored:
        lines.append("| (no candidates scored) | - | - | - | - | - | - | - |")
    return "\n".join(lines)


def _section_5(report: ExplorationReport) -> str:
    lines = ["## 5. Top Candidates by Iteration"]
    for it in report.iterations:
        lines.append(f"\n### Iteration {it.iteration}")
        sorted_sc = sorted(it.scored_candidates, key=lambda s: s.final_score, reverse=True)
        for rank, sc in enumerate(sorted_sc, 1):
            lines.append(
                f"{rank}. **{_truncate(sc.candidate.summary, 60)}** "
                f"(final: {sc.final_score:.2f}, pain: {sc.eval_scores.pain:.1f}, "
                f"diff: {sc.eval_scores.differentiation:.1f})"
            )
    if not report.iterations:
        lines.append("\nNo iterations completed.")
    return "\n".join(lines)


def _section_6(report: ExplorationReport) -> str:
    lines = ["## 6. Merged/Refined Hypotheses"]
    any_merged = False
    for it in report.iterations:
        lines.append(f"\n### Iteration {it.iteration}")
        if it.merged_candidate:
            any_merged = True
            mc = it.merged_candidate
            lines.append(f"\n**Merged hypothesis:** {mc.summary}")
            lines.append(f"- Rationale: {mc.rationale}")
            lines.append("\n| Dimension | Value |")
            lines.append("|---|---|")
            for field, label in _DIMENSION_LABELS:
                lines.append(f"| {label} | {getattr(mc.design_point, field)} |")
        else:
            lines.append("\nNo merge performed this iteration.")
    if not any_merged and not report.iterations:
        lines.append("\nNo merges were performed during exploration.")
    return "\n".join(lines)


def _section_7(report: ExplorationReport) -> str:
    best = report.best_candidate
    dp = best.candidate.design_point
    rows = "\n".join(
        f"| {label} | {getattr(dp, field)} |"
        for field, label in _DIMENSION_LABELS
    )
    return (
        f"## 7. Final Selected Startup Hypothesis\n\n"
        f"**{best.candidate.summary}**\n\n"
        f"| Dimension | Value |\n|---|---|\n{rows}\n\n"
        f"**Final Score:** {best.final_score:.2f}"
    )


def _section_8(report: ExplorationReport) -> str:
    best = report.best_candidate
    e = best.eval_scores
    lines = [
        "## 8. Why This Hypothesis Won",
        "",
        f"This hypothesis achieved a final score of **{best.final_score:.2f}** "
        f"using the scoring function S(x) = R(x;E) - {chr(955)}D(x,x{chr(8320)}) - {chr(956)}C(x):",
        "",
        f"- **Composite reward (R):** {best.composite_score:.2f}",
        f"- **Drift penalty (D):** {best.drift_score:.2f}",
        f"- **Complexity penalty (C):** {best.complexity_score:.2f}",
        "",
        "**Score breakdown:**",
        "",
        f"- Pain: {e.pain:.1f}/10",
        f"- Specificity: {e.specificity:.1f}/10",
        f"- Differentiation: {e.differentiation:.1f}/10",
        f"- Testability: {e.testability:.1f}/10",
        f"- Feasibility: {e.feasibility:.1f}/10",
    ]
    all_scored = _collect_scored(report)
    others = [sc for sc in all_scored if sc.candidate.summary != best.candidate.summary]
    if others:
        runner_up = others[0]
        lines.append("")
        lines.append(
            f"Compared to the runner-up ({_truncate(runner_up.candidate.summary, 40)}, "
            f"score {runner_up.final_score:.2f}), this hypothesis scored higher due to "
            f"a stronger combination of pain intensity and specificity."
        )
    return "\n".join(lines)


def _section_9(report: ExplorationReport) -> str:
    best = report.best_candidate
    all_scored = _collect_scored(report)
    rejected = [sc for sc in all_scored if sc.candidate.summary != best.candidate.summary]
    lines = ["## 9. What Was Rejected and Why"]
    if rejected:
        for sc in rejected:
            weakest_field, weakest_val = _weakest_dimension(sc)
            lines.append(
                f"\n- **{_truncate(sc.candidate.summary, 50)}** "
                f"(score: {sc.final_score:.2f}) — "
                f"weakest dimension: {weakest_field} ({weakest_val:.1f}/10)"
            )
    else:
        lines.append("\nNo candidates were rejected (single candidate evaluated).")
    return "\n".join(lines)


def _section_10(report: ExplorationReport) -> str:
    best = report.best_candidate
    weakest_field, weakest_val = _weakest_dimension(best)
    dp = best.candidate.design_point
    return (
        f"## 10. Riskiest Remaining Assumption\n\n"
        f"The weakest scoring dimension is **{weakest_field}** ({weakest_val:.1f}/10). "
        f"The riskiest assumption is that "
        f"**{getattr(dp, 'customer')}** will actually experience "
        f"**{getattr(dp, 'problem')}** acutely enough to pay for a solution.\n\n"
        f"Falsifiable statement: \"{getattr(dp, 'customer')} rank "
        f"'{getattr(dp, 'problem')}' as a top-3 pain when asked in open-ended interviews.\""
    )


def _section_11(report: ExplorationReport) -> str:
    dp = report.best_candidate.candidate.design_point
    return (
        f"## 11. First Validation Experiment\n\n"
        f"{report.validation_experiment}\n\n"
        f"**Structured plan:**\n\n"
        f"- **Core assumption:** {dp.customer} will pay for {dp.solution}\n"
        f"- **Method:** Customer discovery interviews + problem validation\n"
        f"- **Target customers:** {dp.customer} (find via {dp.gtm_path})\n"
        f"- **Sample size:** 10-15 interviews\n"
        f"- **Key questions:**\n"
        f"  1. How do you currently handle {dp.problem}?\n"
        f"  2. What does this problem cost you (time/money/stress)?\n"
        f"  3. What have you tried to solve it?\n"
        f"  4. How would you describe the ideal solution?\n"
        f"  5. Would you pay for {dp.solution}? How much?\n"
        f"- **Falsification:** If fewer than 3 of 15 respondents rank this as a top-3 pain, "
        f"the hypothesis is invalidated\n"
        f"- **Success:** If 5+ of 15 respondents confirm acute pain and willingness to pay"
    )


def _section_12(report: ExplorationReport) -> str:
    dp = report.best_candidate.candidate.design_point
    return (
        f"## 12. Decision Rule\n\n"
        f"- **CONTINUE** if: 5+ of 15 {dp.customer} confirm acute pain "
        f"and express willingness to pay for {dp.solution}\n"
        f"- **PIVOT** if: Pain is confirmed but the proposed {dp.wedge} is not the right entry point "
        f"(try adjacent segments or different GTM)\n"
        f"- **KILL** if: Fewer than 3 of 15 respondents recognize the problem, "
        f"or all report adequate existing solutions"
    )


def _section_13(report: ExplorationReport) -> str:
    dp = report.best_candidate.candidate.design_point
    return (
        f"## 13. Recommended 7-Day Customer Discovery Plan\n\n"
        f"**Day 1-2: Preparation**\n"
        f"- Build target list of 20-30 {dp.customer}\n"
        f"- Source contacts via {dp.gtm_path}\n"
        f"- Draft interview script with 5-7 open-ended questions\n"
        f"- Set up scheduling (Calendly or direct outreach)\n\n"
        f"**Day 3-5: Interviews**\n"
        f"- Conduct 10-15 customer discovery interviews (30 min each)\n"
        f"- Focus on problem validation, not solution pitching\n"
        f"- Record key quotes and pain severity (1-10 self-rating)\n"
        f"- Track: current solution, switching cost, willingness to pay\n\n"
        f"**Day 6-7: Synthesis & Decision**\n"
        f"- Tabulate results: pain confirmation rate, WTP range, common objections\n"
        f"- Apply decision rule (continue/pivot/kill)\n"
        f"- Write 1-page findings memo with go/no-go recommendation\n"
        f"- If CONTINUE: draft landing page copy using validated language from interviews"
    )


def _budget_appendix(report: ExplorationReport) -> str:
    bs = report.budget_summary
    return (
        f"---\n\n"
        f"**Budget Summary:** {bs.total_calls} agent calls "
        f"({bs.successful_calls} successful, {bs.failed_calls} failed) "
        f"in {bs.total_duration:.1f}s"
    )


def _collect_scored(report: ExplorationReport) -> list[ScoredCandidate]:
    all_scored: list[ScoredCandidate] = []
    for it in report.iterations:
        all_scored.extend(it.scored_candidates)
    all_scored.sort(key=lambda sc: sc.final_score, reverse=True)
    return all_scored


def _weakest_dimension(sc: ScoredCandidate) -> tuple[str, float]:
    e = sc.eval_scores
    scores = {f: getattr(e, f) for f in _SCORE_FIELDS}
    weakest = min(scores, key=scores.__getitem__)
    return weakest, scores[weakest]


def _truncate(s: str, max_len: int) -> str:
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."
