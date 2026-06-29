"""Pydantic v2 strict-mode domain models for ideaopt."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DesignPoint(BaseModel):
    """Structured startup hypothesis with 7 dimensions."""

    model_config = ConfigDict(strict=True, extra="forbid")

    customer: str
    problem: str
    solution: str
    value_prop: str
    wedge: str
    business_model: str
    gtm_path: str


class CandidateHypothesis(BaseModel):
    """A candidate hypothesis with all dimensions, summary, and context."""

    model_config = ConfigDict(strict=True, extra="forbid")

    design_point: DesignPoint
    summary: str
    rationale: str
    iteration: int


class EvalScore(BaseModel):
    """Per-axis evaluation scores, each 0-10."""

    model_config = ConfigDict(strict=True, extra="forbid")

    pain: float = Field(ge=0.0, le=10.0)
    specificity: float = Field(ge=0.0, le=10.0)
    differentiation: float = Field(ge=0.0, le=10.0)
    testability: float = Field(ge=0.0, le=10.0)
    feasibility: float = Field(ge=0.0, le=10.0)
    rationale: str


class ScoredCandidate(BaseModel):
    """Candidate with composite score breakdown."""

    model_config = ConfigDict(strict=True, extra="forbid")

    candidate: CandidateHypothesis
    eval_scores: EvalScore
    composite_score: float
    drift_score: float
    complexity_score: float
    final_score: float


class RunConfig(BaseModel):
    """Budget parameters for an exploration run."""

    model_config = ConfigDict(strict=True, extra="forbid")

    max_iterations: int = 2
    candidates_per_round: int = 5
    top_k: int = 2
    max_agent_calls: int = 30
    agent_timeout: int = 300
    drift_weight: float = 0.15
    complexity_weight: float = 0.1
    model: str | None = None


class BudgetSummary(BaseModel):
    """Summary of resource usage during an exploration run."""

    model_config = ConfigDict(strict=True, extra="forbid")

    total_calls: int
    successful_calls: int
    failed_calls: int
    total_duration: float


class IterationResult(BaseModel):
    """Result of a single exploration iteration."""

    model_config = ConfigDict(strict=True, extra="forbid")

    iteration: int
    candidates: list[CandidateHypothesis]
    scored_candidates: list[ScoredCandidate]
    merged_candidate: CandidateHypothesis | None


class ExplorationReport(BaseModel):
    """Final output of a complete exploration run."""

    model_config = ConfigDict(strict=True, extra="forbid")

    original_idea: str
    design_point: DesignPoint
    iterations: list[IterationResult]
    best_candidate: ScoredCandidate
    validation_experiment: str
    budget_summary: BudgetSummary


class ReportState(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    status: str
    original_idea: str
    design_point: DesignPoint | None = None
    iterations: list[IterationResult] = Field(default_factory=list)
    current_iteration: int = 0
    current_candidates: list[CandidateHypothesis] = Field(default_factory=list)
    current_scored: list[ScoredCandidate] = Field(default_factory=list)
    best_candidate: ScoredCandidate | None = None
    validation_experiment: str = ""
    budget_summary: BudgetSummary | None = None
