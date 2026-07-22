"""MCP tool wrappers for L4 plan / simulate (no MCP SDK required for unit tests)."""

from __future__ import annotations

import json
from typing import Any

from application.plan import get_plan, run_simulation_with_plan

OPTIMIZE_BEDS_SCHEMA: dict[str, Any] = {
    "name": "optimize_beds",
    "description": (
        "ICU bed assignment via CP-SAT. "
        "Without run_id: run simulation then return plan. "
        "With run_id: fetch existing plan from sched.assignments."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "run_id": {
                "type": ["string", "null"],
                "description": "Optional simulation run id; omit to run a new simulation",
            },
        },
        "required": [],
    },
}


def optimize_beds(run_id: str | None = None) -> dict[str, Any]:
    """MCP tool body: optional run_id -> L4 plan JSON."""
    if run_id:
        plan = get_plan(run_id)
        return {"plan": plan, "status": plan.get("status", "ok")}
    return run_simulation_with_plan()


def optimize_beds_json(run_id: str | None = None) -> str:
    return json.dumps(optimize_beds(run_id), ensure_ascii=False, default=str)
