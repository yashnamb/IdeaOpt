"""CLI entry point for ideaopt."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

import structlog

from ideaopt.models import RunConfig
from ideaopt.orchestrator import run_exploration
from ideaopt.report import generate_report

log = structlog.get_logger()


def build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="ideaopt",
        description="Bounded multi-agent optimization of startup hypotheses under drift and budget constraints.",
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run the full exploration loop")
    run_parser.add_argument("idea", help="The startup idea to explore")
    run_parser.add_argument(
        "--iterations", type=int, default=2,
        help="Maximum exploration iterations (default: 2)",
    )
    run_parser.add_argument(
        "--candidates", type=int, default=5,
        help="Candidates per round (default: 5)",
    )
    run_parser.add_argument(
        "--top-k", type=int, default=2,
        help="Top candidates to select per round (default: 2)",
    )
    run_parser.add_argument(
        "--max-agent-calls", type=int, default=30,
        help="Maximum agent calls budget (default: 30)",
    )
    run_parser.add_argument(
        "--timeout", type=int, default=300,
        help="Agent timeout in seconds (default: 300)",
    )
    run_parser.add_argument(
        "--output", type=str, default=None,
        help="Output file path for the report (default: stdout)",
    )
    run_parser.add_argument(
        "--model", type=str, default=None,
        help="Model override (e.g., sonnet, opus)",
    )
    run_parser.add_argument(
        "--verbose", action="store_true",
        help="Enable verbose/debug logging output",
    )

    viz_parser = subparsers.add_parser("visualize", help="Visualize an exploration report")
    viz_parser.add_argument("input", help="Path to ExplorationReport JSON file")
    viz_parser.add_argument(
        "--output", type=str, default=None,
        help="Output HTML file (default: <input>.html)",
    )
    viz_parser.add_argument(
        "--no-open", action="store_true",
        help="Do not auto-open in browser",
    )

    return parser


def main() -> None:
    """Main entry point for the CLI."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "run":
        _configure_logging(verbose=args.verbose)
        _run_exploration(args)
    elif args.command == "visualize":
        _visualize(args)


def _run_exploration(args: argparse.Namespace) -> None:
    config = RunConfig(
        max_iterations=args.iterations,
        candidates_per_round=args.candidates,
        top_k=args.top_k,
        max_agent_calls=args.max_agent_calls,
        agent_timeout=args.timeout,
        model=args.model,
    )

    try:
        if args.output and args.output.endswith(".html"):
            report_path = Path(args.output).resolve()
            log.info("live_report", path=str(report_path))
            print(
                f"Live report: {report_path.as_uri()} — open in browser to watch progress",
                file=sys.stderr,
            )
            report = asyncio.run(run_exploration(args.idea, config, report_path=report_path))
        else:
            report = asyncio.run(run_exploration(args.idea, config))
    except Exception as exc:
        log.error("exploration_failed", error=str(exc))
        sys.exit(1)

    if args.output:
        if args.output.endswith(".html"):
            pass
        elif args.output.endswith(".json"):
            Path(args.output).write_text(report.model_dump_json(indent=2))
        else:
            Path(args.output).write_text(generate_report(report))
        log.info("report_written", path=args.output)
    else:
        print(generate_report(report))

    sys.exit(0)


def _visualize(args: argparse.Namespace) -> None:
    import webbrowser

    from ideaopt.models import ExplorationReport, ReportState
    from ideaopt.visualizer import generate_html

    path = Path(args.input)
    if not path.exists():
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)

    json_data = path.read_text()
    try:
        report = ExplorationReport.model_validate_json(json_data)
    except Exception as exc:
        print(f"Error: invalid report JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    state = ReportState(
        status="complete",
        original_idea=report.original_idea,
        design_point=report.design_point,
        iterations=report.iterations,
        current_iteration=len(report.iterations),
        best_candidate=report.best_candidate,
        validation_experiment=report.validation_experiment,
        budget_summary=report.budget_summary,
    )
    html = generate_html(state)

    out_path = Path(args.output) if args.output else path.with_suffix(".html")
    out_path.write_text(html)
    print(f"Visualization written to {out_path}")

    if not args.no_open:
        webbrowser.open(out_path.as_uri())


def _configure_logging(*, verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(level),
    )


if __name__ == "__main__":
    main()
