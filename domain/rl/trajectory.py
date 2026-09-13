"""Export rolling-horizon transitions for RL trajectory protocol (S2)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from domain.rolling.engine import run_rolling_simulation
from infra.config import load_yaml

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "artifacts" / "trajectories"


def _transition_from_history(history: list[dict], step_hours: int, n_beds: int) -> list[dict]:
    transitions: list[dict] = []
    for i in range(1, len(history)):
        prev, cur = history[i - 1], history[i]
        occupied = int(cur.get("occupied", 0))
        free = max(n_beds - occupied, 0)
        transitions.append(
            {
                "t": int(cur.get("step", i)),
                "dt_hours": int(step_hours),
                "state": {
                    "occupied": occupied,
                    "free_beds": free,
                    "avg_sofa": cur.get("avg_sofa"),
                    "avg_weight": cur.get("avg_weight"),
                },
                "action": {
                    "admitted": int(cur.get("admitted", 0)),
                    "discharged": int(cur.get("discharged", 0)),
                    "policy": "rolling_cp_sat_fill",
                },
                "reward_components": {
                    "occupancy": occupied / max(n_beds, 1),
                    "wait_proxy": float(free),
                },
                "constraint_violation": False,
                "prev_occupied": int(prev.get("occupied", 0)),
            }
        )
    return transitions


def export_rolling_trajectory(
    *,
    n_steps: int = 12,
    out_name: str | None = None,
) -> dict[str, Any]:
    """Run rolling sim and write JSON trajectory pack (not for Git)."""
    opt = load_yaml("optimizer.yaml")
    sim = run_rolling_simulation(n_steps=n_steps)
    step_hours = int(sim.get("step_hours") or opt.get("rolling", {}).get("step_hours", 2))
    n_beds = int(sim.get("n_beds") or opt.get("resources", {}).get("n_beds", 20))
    transitions = _transition_from_history(list(sim.get("history") or []), step_hours, n_beds)
    payload = {
        "protocol_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "domain.rolling.engine.run_rolling_simulation",
        "n_beds": n_beds,
        "step_hours": step_hours,
        "n_steps": int(sim.get("total_steps", n_steps)),
        "summary": {
            "total_admissions": sim.get("total_admissions"),
            "total_discharges": sim.get("total_discharges"),
            "final_occupancy": sim.get("final_occupancy"),
            "bed_utilization_pct": sim.get("bed_utilization_pct"),
        },
        "transitions": transitions,
        "notes": [
            "Offline demo trajectory from rolling CP-SAT fill heuristic.",
            "Not a MIMIC bedside event log; see docs/TRAJECTORY_PROTOCOL.md.",
            "Do not claim online MIMIC-PPO from this pack alone.",
        ],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    name = out_name or f"rolling_traj_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    path = OUT_DIR / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    latest = OUT_DIR / "rolling_traj_latest.json"
    latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "ok", "path": str(path), "latest": str(latest), "n_transitions": len(transitions)}
