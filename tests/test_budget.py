"""Tests for BudgetTracker."""

from __future__ import annotations

from ideaopt.budget import BudgetTracker
from ideaopt.models import BudgetSummary


class TestBudgetTracker:
    def test_initial_state(self) -> None:
        bt = BudgetTracker(max_iterations=3, max_agent_calls=20)
        assert bt.can_continue()
        assert bt.calls_remaining == 20
        assert bt.iterations_completed == 0

    def test_track_successful_call(self) -> None:
        bt = BudgetTracker(max_iterations=2, max_agent_calls=10)
        bt.track_call("encoder", 1.5, success=True)
        s = bt.summary()
        assert s.total_calls == 1
        assert s.successful_calls == 1
        assert s.failed_calls == 0
        assert s.total_duration == 1.5

    def test_track_failed_call(self) -> None:
        bt = BudgetTracker(max_iterations=2, max_agent_calls=10)
        bt.track_call("validator", 0.8, success=False)
        s = bt.summary()
        assert s.total_calls == 1
        assert s.successful_calls == 0
        assert s.failed_calls == 1

    def test_exhausts_agent_calls(self) -> None:
        bt = BudgetTracker(max_iterations=10, max_agent_calls=3)
        bt.track_call("a", 1.0, success=True)
        bt.track_call("b", 1.0, success=True)
        assert bt.can_continue()
        bt.track_call("c", 1.0, success=True)
        assert not bt.can_continue()

    def test_exhausts_iterations(self) -> None:
        bt = BudgetTracker(max_iterations=2, max_agent_calls=100)
        bt.complete_iteration()
        assert bt.can_continue()
        bt.complete_iteration()
        assert not bt.can_continue()

    def test_calls_remaining_never_negative(self) -> None:
        bt = BudgetTracker(max_iterations=2, max_agent_calls=1)
        bt.track_call("a", 1.0, success=True)
        bt.track_call("b", 1.0, success=True)
        assert bt.calls_remaining == 0

    def test_summary_returns_budget_summary_model(self) -> None:
        bt = BudgetTracker(max_iterations=2, max_agent_calls=10)
        bt.track_call("encoder", 2.555, success=True)
        bt.track_call("validator", 1.111, success=False)
        s = bt.summary()
        assert isinstance(s, BudgetSummary)
        assert s.total_calls == 2
        assert s.successful_calls == 1
        assert s.failed_calls == 1
        assert s.total_duration == 3.67

    def test_complete_iteration_increments(self) -> None:
        bt = BudgetTracker(max_iterations=5, max_agent_calls=50)
        for _ in range(3):
            bt.complete_iteration()
        assert bt.iterations_completed == 3

    def test_mixed_budget_exhaustion(self) -> None:
        bt = BudgetTracker(max_iterations=2, max_agent_calls=5)
        bt.complete_iteration()
        for i in range(5):
            bt.track_call(f"agent_{i}", 0.5, success=True)
        assert not bt.can_continue()
        assert bt.iterations_completed == 1
