"""Export rolling-horizon transitions for RL trajectory protocol (S2)."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any

from domain.rolling.engine import run_rolling_simulation
from infra.config import load_yaml

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "artifacts" / "trajectories"
PROTOCOL_VERSION = "2.0"
MAX_EXPORT_STEPS = 10_000
_WINDOWS_RESERVED_STEMS = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"} | {
    f"{prefix}{digit}" for prefix in ("COM", "LPT") for digit in "123456789¹²³"
}


def _validate_export_request(n_steps: int, out_name: str | None) -> None:
    if isinstance(n_steps, bool) or not isinstance(n_steps, int) or not 0 <= n_steps <= MAX_EXPORT_STEPS:
        raise ValueError(f"n_steps must be an integer between 0 and {MAX_EXPORT_STEPS}")
    if out_name is None:
        return
    if (
        not isinstance(out_name, str)
        or not out_name
        or len(out_name) > 255
        or out_name != out_name.strip()
        or any(ord(char) < 32 or char in '\\/<>:"|?*' for char in out_name)
        or out_name.split(".", 1)[0].rstrip(" ").upper() in _WINDOWS_RESERVED_STEMS
        or PureWindowsPath(out_name).suffix.lower() != ".json"
    ):
        raise ValueError("out_name must be a legal JSON basename in the trajectory directory")


def _constraint_violation(snapshot: dict) -> bool | None:
    result = snapshot.get("constraint_violation")
    # Only an explicit boolean from the engine is a checked result.
    return result if isinstance(result, bool) else None


def _state_from_snapshot(snapshot: dict, n_beds: int) -> dict:
    occupied = int(snapshot.get("occupied", 0))
    state = {
        "occupied": occupied,
        "free_beds": max(n_beds - occupied, 0),
        "avg_sofa": snapshot.get("avg_sofa"),
        "avg_weight": snapshot.get("avg_weight"),
        "constraint_violation": _constraint_violation(snapshot),
    }
    if "assignments" in snapshot:
        state["assignments"] = deepcopy(snapshot["assignments"])
    return state


def _transition_from_history(history: list[dict], step_hours: int, n_beds: int) -> list[dict]:
    transitions: list[dict] = []
    for i in range(1, len(history)):
        prev, cur = history[i - 1], history[i]
        state = _state_from_snapshot(prev, n_beds)
        next_state = _state_from_snapshot(cur, n_beds)
        violation = next_state["constraint_violation"]
        action = {
            "admitted": int(cur.get("admitted", 0)),
            "discharged": int(cur.get("discharged", 0)),
            "policy": "rolling_cp_sat_fill",
        }
        for key in (
            "admitted_stay_ids",
            "discharged_stay_ids",
            "returned_to_queue_stay_ids",
            "solver_status",
        ):
            if key in cur:
                action[key] = deepcopy(cur[key])
        transitions.append(
            {
                "t": int(cur.get("step", i)),
                "dt_hours": int(step_hours),
                "state": state,
                "next_state": next_state,
                "action": action,
                "reward_components": {
                    "occupancy": next_state["occupied"] / max(n_beds, 1),
                    # Legacy alias: free beds, not priority_served or waiting time.
                    "wait": float(next_state["free_beds"]),
                    "wait_proxy": float(next_state["free_beds"]),
                },
                "constraint_violation": violation,
                "constraint_check_status": "checked" if violation is not None else "unknown",
                "prev_occupied": state["occupied"],
            }
        )
    return transitions


def export_rolling_trajectory(
    *,
    n_steps: int = 12,
    out_name: str | None = None,
) -> dict[str, Any]:
    """Export a simulation without sched writes; database reads are still required."""
    _validate_export_request(n_steps, out_name)
    name = out_name if out_name is not None else (
        f"rolling_traj_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    out_dir = OUT_DIR.resolve()
    path = out_dir / name
    latest = out_dir / "rolling_traj_latest.json"
    # Also reject pre-existing file links that would redirect either write outside.
    if any(target.resolve().parent != out_dir for target in (path, latest)):
        raise ValueError("trajectory output must stay inside the trajectory directory")
    opt = load_yaml("optimizer.yaml")
    sim = run_rolling_simulation(n_steps=n_steps, persist=False)
    step_hours = int(sim.get("step_hours") or opt.get("rolling", {}).get("step_hours", 2))
    n_beds = int(sim.get("n_beds") or opt.get("resources", {}).get("n_beds", 20))
    transitions = _transition_from_history(list(sim.get("history") or []), step_hours, n_beds)
    payload = {
        "protocol_version": PROTOCOL_VERSION,
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
        "reward_semantics": {
            "occupancy": "Unweighted next_state.occupied / n_beds utilization proxy.",
            "wait": "Legacy alias of wait_proxy: next_state.free_beds, not priority_served or waiting time.",
            "wait_proxy": "Unweighted next_state.free_beds; not an ICUEnv/PPO training reward.",
        },
        "notes": [
            "Offline demo trajectory from rolling CP-SAT simulation; persist=False disables sched writes.",
            "Protocol 2.0: state is before the transition; next_state is after it (1.0 state was after).",
            "constraint_violation reflects the engine's next-state check; null means unknown, not passed.",
            "Reward components are unweighted proxies, not evidence of RL training reward alignment.",
            "Not a MIMIC bedside event log; see docs/TRAJECTORY_PROTOCOL.md.",
            "Do not claim online MIMIC-PPO from this pack alone.",
        ],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    path.write_text(serialized, encoding="utf-8")
    latest.write_text(serialized, encoding="utf-8")
    return {"status": "ok", "path": str(path), "latest": str(latest), "n_transitions": len(transitions)}
