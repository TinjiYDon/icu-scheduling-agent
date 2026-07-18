"""Unified application entry point for CP-SAT and trained PPO policies."""

from __future__ import annotations

from domain.optimizer.cp_sat import run_assignment
from infra.config import load_yaml


def optimize(policy: str | None = None, model_path: str | None = None) -> dict:
    selected = policy or str(
        load_yaml("optimizer.yaml").get("policy", {}).get("default", "cp_sat")
    )
    if selected == "cp_sat":
        result = run_assignment()
        result["policy"] = "cp_sat"
        return result
    if selected == "ppo":
        from application.run_ppo import run_ppo

        return run_ppo(model_path=model_path)
    if selected == "hybrid":
        raise NotImplementedError("hybrid policy is reserved but not implemented")
    raise ValueError(f"unsupported scheduling policy: {selected}")
