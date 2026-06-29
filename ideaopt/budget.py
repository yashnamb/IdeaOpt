"""Budget tracking for agent calls during exploration runs."""

from __future__ import annotations

import time

import structlog

from ideaopt.models import BudgetSummary

log = structlog.get_logger()


class BudgetTracker:
    """Tracks agent call budget and iteration count."""

    def __init__(self, max_iterations: int, max_agent_calls: int) -> None:
        self._max_iterations = max_iterations
        self._max_agent_calls = max_agent_calls
        self._iterations_completed = 0
        self._total_calls = 0
        self._successful_calls = 0
        self._failed_calls = 0
        self._total_duration = 0.0
        self._start_time = time.monotonic()

    def track_call(self, role: str, duration: float, success: bool) -> None:
        self._total_calls += 1
        self._total_duration += duration
        if success:
            self._successful_calls += 1
        else:
            self._failed_calls += 1
        log.debug(
            "budget_track_call",
            role=role,
            duration=round(duration, 2),
            success=success,
            calls_remaining=self._max_agent_calls - self._total_calls,
        )

    def complete_iteration(self) -> None:
        self._iterations_completed += 1
        log.info(
            "budget_iteration_complete",
            iteration=self._iterations_completed,
            max_iterations=self._max_iterations,
        )

    def can_continue(self) -> bool:
        if self._iterations_completed >= self._max_iterations:
            log.info("budget_exhausted", reason="max_iterations")
            return False
        if self._total_calls >= self._max_agent_calls:
            log.info("budget_exhausted", reason="max_agent_calls")
            return False
        return True

    @property
    def calls_remaining(self) -> int:
        return max(0, self._max_agent_calls - self._total_calls)

    @property
    def iterations_completed(self) -> int:
        return self._iterations_completed

    def summary(self) -> BudgetSummary:
        return BudgetSummary(
            total_calls=self._total_calls,
            successful_calls=self._successful_calls,
            failed_calls=self._failed_calls,
            total_duration=round(self._total_duration, 2),
        )
