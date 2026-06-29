"""Tests for the CLI entry point."""

from __future__ import annotations

import subprocess
import sys

from ideaopt.cli import build_parser


class TestArgParsing:
    def test_run_defaults(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["run", "my startup idea"])
        assert args.command == "run"
        assert args.idea == "my startup idea"
        assert args.iterations == 2
        assert args.candidates == 5
        assert args.top_k == 2
        assert args.max_agent_calls == 30
        assert args.timeout == 300
        assert args.output is None
        assert args.model is None
        assert args.verbose is False

    def test_run_all_options(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "run", "test idea",
            "--iterations", "3",
            "--candidates", "10",
            "--top-k", "3",
            "--max-agent-calls", "50",
            "--timeout", "600",
            "--output", "report.md",
            "--model", "sonnet",
            "--verbose",
        ])
        assert args.idea == "test idea"
        assert args.iterations == 3
        assert args.candidates == 10
        assert args.top_k == 3
        assert args.max_agent_calls == 50
        assert args.timeout == 600
        assert args.output == "report.md"
        assert args.model == "sonnet"
        assert args.verbose is True

    def test_no_command_parsed(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.command is None


class TestVisualizeArgParsing:
    def test_visualize_parser(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["visualize", "report.json"])
        assert args.command == "visualize"
        assert args.input == "report.json"
        assert args.output is None
        assert args.no_open is False

    def test_visualize_with_output(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["visualize", "report.json", "--output", "out.html"])
        assert args.output == "out.html"

    def test_visualize_no_open(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["visualize", "report.json", "--no-open"])
        assert args.no_open is True


class TestCLISubprocess:
    def test_help_exits_zero(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "ideaopt", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "ideaopt" in result.stdout.lower()

    def test_run_help(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "ideaopt", "run", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "--iterations" in result.stdout
        assert "--model" in result.stdout
        assert "--verbose" in result.stdout

    def test_no_command_exits_nonzero(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "ideaopt"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1

    def test_run_missing_idea_exits_nonzero(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "ideaopt", "run"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0

    def test_visualize_help(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "ideaopt", "visualize", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "visualize" in result.stdout.lower()

    def test_cli_module_help(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "ideaopt.cli", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "ideaopt" in result.stdout.lower()
