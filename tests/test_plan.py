"""L4 plan API tests — no database required.

`get_plan(run_id=...)` previously hit PostgreSQL even for the "run does not
exist" path, because `run_exists()` opens a connection before it can answer.
That made this file unrunnable in CI (workflow step "Unit tests (no DB)"),
and the job had been failing red since 2026-09-24.

The `run_exists` lookup is stubbed with the same FakeEngine pattern already
used in `test_cp_sat_split.py`, so the not-found branch is exercised purely
in-process.
"""

from __future__ import annotations

import pytest


class _FakeResult:
    def __init__(self, value: int) -> None:
        self._value = value

    def scalar_one(self) -> int:
        return self._value


class _FakeConn:
    def __init__(self, count: int) -> None:
        self._count = count

    def execute(self, *_args, **_kwargs) -> _FakeResult:
        return _FakeResult(self._count)

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> bool:
        return False


class _FakeEngine:
    """Answers the COUNT(*) probe with a fixed row count."""

    def __init__(self, count: int = 0) -> None:
        self._count = count

    def connect(self) -> _FakeConn:
        return _FakeConn(self._count)


def test_plan_module_imports():
    from application.plan import get_plan, run_simulation_with_plan
    from data_access.assignments_repo import fetch_assignments, latest_run_id

    assert callable(get_plan)
    assert callable(run_simulation_with_plan)
    assert callable(fetch_assignments)
    assert callable(latest_run_id)


@pytest.mark.parametrize(
    ("row_count", "expected_status"),
    [
        (0, "not_found"),
        (1, "ok"),
    ],
)
def test_get_plan_resolves_existence_via_stubbed_db(
    monkeypatch, row_count, expected_status
):
    """Existence probe drives the branch; nothing touches a real socket."""
    from application.plan import get_plan
    import application.plan as plan_mod
    import data_access.assignments_repo as repo

    monkeypatch.setattr(repo, "get_engine", lambda: _FakeEngine(row_count))
    monkeypatch.setattr(
        plan_mod, "fetch_assignments", lambda _rid: [{"bed_id": "B1"}] * row_count
    )

    out = get_plan(run_id="__nonexistent_run__")
    assert out["status"] == expected_status
    assert len(out["assignments"]) == row_count


def test_get_plan_not_found(monkeypatch):
    from application.plan import get_plan
    import data_access.assignments_repo as repo

    monkeypatch.setattr(repo, "get_engine", lambda: _FakeEngine(0))

    out = get_plan(run_id="__nonexistent_run__")
    assert out["assignments"] == []
    assert out["status"] == "not_found"