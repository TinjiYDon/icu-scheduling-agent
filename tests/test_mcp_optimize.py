from unittest.mock import patch

from presentation.mcp_tools import OPTIMIZE_BEDS_SCHEMA, optimize_beds


def test_optimize_beds_schema():
    assert OPTIMIZE_BEDS_SCHEMA["name"] == "optimize_beds"
    assert "run_id" in OPTIMIZE_BEDS_SCHEMA["inputSchema"]["properties"]


def test_optimize_beds_runs_simulation_when_no_run_id():
    fake = {"simulate": {"run_id": "r1"}, "plan": {"status": "ok"}, "status": "ok"}
    with patch(
        "presentation.mcp_tools.run_simulation_with_plan", return_value=fake
    ) as mocked:
        out = optimize_beds(None)
    mocked.assert_called_once_with()
    assert out["status"] == "ok"
    assert out["plan"]["status"] == "ok"


def test_optimize_beds_fetches_plan_when_run_id():
    fake_plan = {"run_id": "r9", "assignments": [], "metrics": {"assigned": 0}, "status": "ok"}
    with patch("presentation.mcp_tools.get_plan", return_value=fake_plan) as mocked:
        out = optimize_beds("r9")
    mocked.assert_called_once_with("r9")
    assert out["plan"]["run_id"] == "r9"
    assert out["status"] == "ok"
