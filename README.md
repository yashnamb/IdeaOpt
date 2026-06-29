# IdeaOpt

Bounded multi-agent optimization of startup hypotheses under drift and budget constraints.

> Built at the [AGI House Multi-Agent Orchestration Build Day](https://app.agihouse.org/events/multi-agent-orchestration-build-day) hackathon.

## What it does

IdeaOpt treats startup idea refinement as a **design space exploration problem**. It is not a chatbot and not a one-shot report generator. It runs an iterative search that generates candidate hypotheses, evaluates them across multiple axes (pain, specificity, differentiation, testability, feasibility), merges the strongest components, and refines under budget constraints.

Each hypothesis is a 7-dimensional design point: customer, problem, solution, value prop, wedge, business model, and GTM path. The system explores the space around your initial idea while penalizing drift from the original and kitchen-sink complexity.

## Scoring

Every candidate is scored with a composite function:

```
S(x) = R(x; E) - λ·D(x, x₀) - μ·C(x)
```

| Term | Meaning |
|------|---------|
| **R(x; E)** | Reward — weighted average of evaluator scores (pain 30%, specificity 20%, differentiation 20%, testability 15%, feasibility 15%) |
| **D(x, x₀)** | Drift — dimension-by-dimension distance from the original idea. Penalizes candidates that wander too far from founder intent |
| **C(x)** | Complexity — penalizes over-scoped ideas. Longer, vaguer descriptions score higher complexity |
| **λ** | Drift weight (default: 0.15) |
| **μ** | Complexity weight (default: 0.10) |

## How it works

```
         ┌──────────────────────────────────────┐
         │           Original Idea              │
         └──────────────┬───────────────────────┘
                        │
                        ▼
                ┌───────────────┐
                │    Encode     │  → DesignPoint (7 dimensions)
                └───────┬───────┘
                        │
          ┌─────────────┼─────────────┐
          │             ▼             │
          │     ┌───────────────┐     │
          │     │   Generate    │     │  → 3-5 candidate hypotheses
          │     └───────┬───────┘     │
          │             ▼             │
          │     ┌───────────────┐     │
          │     │   Evaluate    │     │  → score each across 5 axes
          │     └───────┬───────┘     │     (3 evaluators in parallel)
          │             ▼             │
          │     ┌───────────────┐     │
          │     │    Select     │     │  → top-k by S(x)
          │     └───────┬───────┘     │
          │             ▼             │
          │     ┌───────────────┐     │
          │     │    Merge      │     │  → combine strongest components
          │     └───────┬───────┘     │
          │             │             │
          │     budget left?          │
          │     score improving?      │
          └─────── yes ◄──────────────┘
                   no ──► stop
                        │
                        ▼
                ┌───────────────┐
                │    Report     │  → 13-section markdown report
                └───────────────┘
```

The loop stops when: budget is exhausted, score plateaus (improvement < 0.5), or the same candidate wins two consecutive rounds.

## Specialist Agents

Seven Claude Code subprocesses, each with a focused prompt:

| Agent | Role |
|-------|------|
| **encoder** | Extracts a structured 7-dimension DesignPoint from raw idea text |
| **generator** | Produces 3-5 candidate hypotheses exploring different wedges, customers, or problem framings |
| **validator** | Scores desirability — is this a painkiller or a vitamin? |
| **competitor** | Researches real competitors via web search and scores differentiation |
| **customer_discovery** | Scores testability/feasibility and designs a concrete 1-2 week validation experiment |
| **merger** | Combines the strongest components from top-k candidates into a more focused hypothesis |
| **report** | Generates a 13-section Startup Hypothesis Design Space Report |

## Quick Start

```bash
# Install
pip install -e .

# Run
ideaopt run "AI receptionist for dental clinics"

# With options
ideaopt run "AI receptionist for dental clinics" \
  --iterations 3 \
  --candidates 5 \
  --top-k 2 \
  --output report.md \
  --verbose
```

### CLI Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--iterations` | 2 | Maximum exploration iterations |
| `--candidates` | 5 | Candidates generated per round |
| `--top-k` | 2 | Top candidates selected per round |
| `--max-agent-calls` | 30 | Total agent call budget |
| `--timeout` | 300 | Agent timeout in seconds |
| `--output` | stdout | Output file path for the report |
| `--model` | None | Model override (e.g., `sonnet`, `opus`) |
| `--verbose` | false | Enable debug logging |

## Example Output

Given the input `"AI receptionist for dental clinics"`, IdeaOpt might converge on:

**Final Hypothesis:**
> Revenue recovery assistant for independent dental clinics that handles missed-call follow-up and incomplete treatment-plan recovery, without requiring practice management system integration.

**Design Point:**
- **Customer:** Independent dental clinics with 1-3 dentists and no dedicated call center
- **Problem:** Missed calls and incomplete treatment plans causing revenue leakage
- **Solution:** AI-powered missed-call follow-up and treatment-plan recovery via SMS/phone
- **Value Prop:** Recover lost revenue without hiring additional staff
- **Wedge:** Missed-call recovery — narrow, testable, immediate ROI
- **Business Model:** Monthly SaaS subscription, per-location pricing
- **GTM Path:** Direct outreach to dental offices via dental associations and practice management consultants

**Validation Experiment:**
1. Interview 15 independent dental clinics (1-3 dentists, no office manager)
2. Core question: Do you track missed calls? How many per week? Do you consider it a revenue problem?
3. **Kill if:** Fewer than 3 of 15 rank missed calls as a top-3 operational pain
4. **Continue if:** 5+ confirm it as a top-3 pain AND 3+ agree to a demo AND 1-2 are open to a paid pilot

## Requirements

- Python 3.11+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated

## Installation

```bash
pip install -e .
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv sync --group dev
```

## Architecture

Three-layer separation:

```
┌─────────────────────────────────────────────────────┐
│  Layer 1 — CLI (ideaopt/cli.py)                     │
│  Pure tools, argparse, asyncio.run() entry point    │
├─────────────────────────────────────────────────────┤
│  Layer 2 — Orchestrator (ideaopt/orchestrator.py)   │
│  Generate→Evaluate→Select→Merge→Refine loop         │
│  Scoring, budget tracking, stop conditions          │
├─────────────────────────────────────────────────────┤
│  Layer 3 — Agents (ideaopt/agents/runner.py)        │
│  Claude Code CLI subprocesses                       │
│  Each agent has a prompt in ideaopt/agents/prompts/ │
└─────────────────────────────────────────────────────┘
```

Agents are invoked as Claude Code CLI subprocesses, not via the Anthropic Python SDK. Each agent receives a task as JSON via stdin and returns structured JSON output.

## Budget Defaults

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_iterations` | 2 | Exploration rounds before stopping |
| `candidates_per_round` | 5 | Hypotheses generated per iteration |
| `top_k` | 2 | Candidates selected for merging |
| `max_agent_calls` | 30 | Hard ceiling on total agent invocations |
| `agent_timeout` | 300s | Per-agent timeout |
| `drift_weight` (λ) | 0.15 | Penalty for drifting from original idea |
| `complexity_weight` (μ) | 0.10 | Penalty for kitchen-sink scope |

## License

MIT
