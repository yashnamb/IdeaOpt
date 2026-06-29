"""Tests for agent prompt files."""

from __future__ import annotations

from pathlib import Path

import pytest

PROMPTS_DIR = Path(__file__).parent.parent / "ideaopt" / "agents" / "prompts"

REQUIRED_ROLES = [
    "encoder",
    "generator",
    "validator",
    "competitor",
    "customer_discovery",
    "merger",
    "report",
]


@pytest.fixture(params=REQUIRED_ROLES)
def prompt_path(request: pytest.FixtureRequest) -> Path:
    return PROMPTS_DIR / f"{request.param}.md"


class TestPromptFilesExist:
    def test_prompts_directory_exists(self) -> None:
        assert PROMPTS_DIR.is_dir()

    def test_prompt_file_exists(self, prompt_path: Path) -> None:
        assert prompt_path.exists(), f"Missing prompt: {prompt_path.name}"

    def test_prompt_file_not_empty(self, prompt_path: Path) -> None:
        content = prompt_path.read_text()
        assert len(content.strip()) > 100, f"Prompt too short: {prompt_path.name}"


class TestPromptContent:
    def test_contains_output_schema(self, prompt_path: Path) -> None:
        content = prompt_path.read_text().lower()
        has_schema = "output schema" in content or "output format" in content
        assert has_schema, f"No output schema section in {prompt_path.name}"

    def test_references_original_idea(self, prompt_path: Path) -> None:
        content = prompt_path.read_text()
        has_reference = "original" in content.lower() and (
            "x₀" in content or "idea" in content.lower()
        )
        assert has_reference, f"No original idea reference in {prompt_path.name}"

    def test_contains_json_schema_or_markdown_format(self, prompt_path: Path) -> None:
        content = prompt_path.read_text()
        has_json = "```json" in content
        has_markdown = "```markdown" in content
        assert has_json or has_markdown, f"No structured format in {prompt_path.name}"


class TestEvaluatorPrompts:
    """Tests specific to evaluator agent prompts that must output EvalScore."""

    EVALUATOR_ROLES = ["validator", "competitor", "customer_discovery"]

    @pytest.fixture(params=EVALUATOR_ROLES)
    def evaluator_path(self, request: pytest.FixtureRequest) -> Path:
        return PROMPTS_DIR / f"{request.param}.md"

    def test_contains_scoring_rubric(self, evaluator_path: Path) -> None:
        content = evaluator_path.read_text().lower()
        assert "rubric" in content or "scoring" in content, (
            f"No scoring rubric in {evaluator_path.name}"
        )

    def test_contains_eval_score_fields(self, evaluator_path: Path) -> None:
        content = evaluator_path.read_text()
        for field in ["pain", "specificity", "differentiation", "testability", "feasibility"]:
            assert field in content, f"Missing EvalScore field '{field}' in {evaluator_path.name}"

    def test_contains_rationale_field(self, evaluator_path: Path) -> None:
        content = evaluator_path.read_text()
        assert "rationale" in content, f"Missing rationale field in {evaluator_path.name}"


class TestSpecificPrompts:
    def test_encoder_has_design_point_fields(self) -> None:
        content = (PROMPTS_DIR / "encoder.md").read_text()
        for field in [
            "customer",
            "problem",
            "solution",
            "value_prop",
            "wedge",
            "business_model",
            "gtm_path",
        ]:
            assert field in content, f"Missing DesignPoint field '{field}' in encoder.md"

    def test_generator_specifies_candidate_count(self) -> None:
        content = (PROMPTS_DIR / "generator.md").read_text()
        assert "3" in content and "5" in content, "Generator should specify 3-5 candidates"

    def test_merger_has_focus_instruction(self) -> None:
        content = (PROMPTS_DIR / "merger.md").read_text()
        assert "MORE focused" in content, "Merger must instruct: more focused, not less"

    def test_report_has_all_13_sections(self) -> None:
        content = (PROMPTS_DIR / "report.md").read_text()
        required_sections = [
            "Original Founder Idea",
            "Extracted Design Dimensions",
            "Candidate Hypotheses Generated",
            "Evaluation Score Table",
            "Top Candidates by Iteration",
            "Merged/Refined Hypotheses",
            "Final Selected Startup Hypothesis",
            "Why This Hypothesis Won",
            "What Was Rejected and Why",
            "Riskiest Remaining Assumption",
            "First Validation Experiment",
            "Decision Rule",
            "7-Day Customer Discovery Plan",
        ]
        for section in required_sections:
            assert section in content, f"Missing report section: '{section}'"

    def test_competitor_instructs_web_search(self) -> None:
        content = (PROMPTS_DIR / "competitor.md").read_text().lower()
        assert "search" in content, "Competitor agent should instruct web search"

    def test_customer_discovery_has_experiment_design(self) -> None:
        content = (PROMPTS_DIR / "customer_discovery.md").read_text().lower()
        assert "experiment" in content, "Customer discovery must include experiment design"
        assert "falsif" in content, "Customer discovery must include falsification criteria"
