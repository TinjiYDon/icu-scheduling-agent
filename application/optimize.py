"""Unified application entry point for the CP-SAT scheduling policy."""

from __future__ import annotations

from domain.optimizer.cp_sat import run_assignment
from infra.config import load_yaml


def optimize(policy: str | None = None) -> dict:
    selected = policy or str(
        load_yaml("optimizer.yaml").get("policy", {}).get("default", "cp_sat")
    )
    if selected == "cp_sat":
        result = run_assignment()
        result["policy"] = "cp_sat"
        return result
    raise ValueError(f"unsupported scheduling policy: {selected}")
