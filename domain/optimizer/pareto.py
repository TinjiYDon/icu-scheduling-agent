"""Anchor solves and payoff table for multi-objective CP-SAT.

P3 computes two sets of anchors:

* **pure anchors**: optimize one objective with no other constraints.  These
  define the mathematical ideal point used for normalization.
* **practical anchors**: same, but with an occupancy floor
  (``f0 >= guard_ratio * f0_ideal``).  These avoid degenerate solutions such as
  "assign nobody to minimize overload" and define a realistic epsilon range.
"""

from __future__ import annotations

import json
import math
import uuid
from pathlib import Path
from typing import Mapping

from domain.optimizer.cp_sat import run_assignment
from domain.optimizer.objectives import OBJECTIVES

# Objective name -> key in run_assignment()["objective"]
OBJECTIVE_KEYS = {
    "occupancy": "f0_occupancy",
    "wait": "f1_priority_total",
    "overload": "f2_overload_penalty",
    "balance": "f3_balance_deviation",
    "zone_mismatch": "f4_zone_mismatch",
    "move": "f5_move",
}

_META_KEYS = (
    "solver_status",
    "objective_mode",
    "pivot",
    "epsilon",
    "assigned",
    "n_stays",
    "lambda",
    "candidate_mode",
    "candidate_seed",
    "candidate_size",
    "priority_mode",
    "wait_source",
    "isolation_mode",
    "n_iso_required",
    "vent_mode",
    "n_vent_required",
    "split",
    "split_meta",
    "objective_scaling",
    "evaluation",
    "resources",
)


def objective_vector(result: Mapping) -> dict[str, float]:
    """Extract the six objective values in a stable order."""
    obj = result["objective"]
    return {name: obj[key] for name, key in OBJECTIVE_KEYS.items()}


def _anchor_record(result: Mapping) -> dict:
    record = {
        "objectives": objective_vector(result),
        "top_assignments": result.get("top_assignments", []),
    }
    for key in _META_KEYS:
        record[key] = result.get(key)
    return record


def _ideal_nadir(anchors: Mapping[str, Mapping]) -> tuple[dict, dict]:
    ideal: dict[str, float] = {}
    nadir: dict[str, float] = {}
    for name, spec in OBJECTIVES.items():
        values = [float(a["objectives"][name]) for a in anchors.values()]
        if spec.sense == "max":
            ideal[name], nadir[name] = max(values), min(values)
        else:
            ideal[name], nadir[name] = min(values), max(values)
    return ideal, nadir


def _degenerate(ideal: Mapping[str, float], nadir: Mapping[str, float]) -> list[str]:
    return [
        name
        for name in OBJECTIVES
        if float(nadir[name]) == float(ideal[name])
    ]


def solve_anchors(
    *,
    practical_guard_ratio: float = 0.9,
    persist: bool = False,
    **run_kwargs,
) -> dict:
    """Solve pure and practical anchors for all six objectives."""
    for forbidden in ("pivot", "epsilon"):
        if forbidden in run_kwargs:
            raise ValueError(f"{forbidden} is managed internally by solve_anchors")

    run_id = f"anchor_{uuid.uuid4().hex[:8]}"

    pure: dict[str, dict] = {}
    for name in OBJECTIVES:
        result = run_assignment(pivot=name, persist=persist, **run_kwargs)
        pure[name] = _anchor_record(result)

    ideal_pure, nadir_pure = _ideal_nadir(pure)

    guard_min = max(1, int(math.floor(practical_guard_ratio * ideal_pure["occupancy"])))

    practical: dict[str, dict] = {}
    for name in OBJECTIVES:
        if name == "occupancy":
            practical[name] = pure[name]
            continue
        result = run_assignment(
            pivot=name,
            epsilon={"occupancy": guard_min},
            persist=persist,
            **run_kwargs,
        )
        practical[name] = _anchor_record(result)

    ideal_practical, nadir_practical = _ideal_nadir(practical)

    payoff_table = {
        name: {anchor: pure[anchor]["objectives"][name] for anchor in pure}
        for name in OBJECTIVES
    }
    payoff_table_practical = {
        name: {anchor: practical[anchor]["objectives"][name] for anchor in practical}
        for name in OBJECTIVES
    }

    first = next(iter(pure.values()))
    config = {
        key: first.get(key)
        for key in (
            "candidate_mode",
            "candidate_seed",
            "candidate_size",
            "priority_mode",
            "wait_source",
            "isolation_mode",
            "vent_mode",
            "split",
        )
    }

    return {
        "run_id": run_id,
        "config": config,
        "guard": {
            "ratio": practical_guard_ratio,
            "occupancy_min": guard_min,
        },
        "pure": pure,
        "practical": practical,
        "ideal": ideal_pure,
        "nadir": nadir_pure,
        "practical_ideal": ideal_practical,
        "practical_nadir": nadir_practical,
        "payoff_table": payoff_table,
        "payoff_table_practical": payoff_table_practical,
        "degenerate": {
            "pure": _degenerate(ideal_pure, nadir_pure),
            "practical": _degenerate(ideal_practical, nadir_practical),
        },
    }


def save_anchors(result: Mapping, path: str | Path | None = None) -> Path:
    """Persist an anchor result as JSON."""
    if path is None:
        path = Path("reports") / "pareto" / f"anchors_{result['run_id']}.json"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return path


def format_payoff(result: Mapping) -> str:
    """Render compact payoff tables for terminal output."""
    names = list(OBJECTIVES)

    def table(anchors: Mapping) -> list[str]:
        header = "anchor".ljust(14) + "".join(n.rjust(12) for n in names)
        lines = [header, "-" * len(header)]
        for anchor in names:
            row = anchor.ljust(14)
            row += "".join(
                f"{anchors[anchor]['objectives'][n]:>12.2f}" for n in names
            )
            lines.append(row)
        return lines

    lines = ["[pure anchors]"]
    lines += table(result["pure"])
    lines += ["", "[practical anchors]"]
    lines += table(result["practical"])
    lines += [""]
    lines.append("ideal:     " + "  ".join(f"{n}={result['ideal'][n]:.2f}" for n in names))
    lines.append("nadir:     " + "  ".join(f"{n}={result['nadir'][n]:.2f}" for n in names))
    lines.append(
        "practical ideal: "
        + "  ".join(f"{n}={result['practical_ideal'][n]:.2f}" for n in names)
    )
    lines.append(
        "practical nadir: "
        + "  ".join(f"{n}={result['practical_nadir'][n]:.2f}" for n in names)
    )
    lines.append("degenerate (pure):      " + ", ".join(result["degenerate"]["pure"]))
    lines.append(
        "degenerate (practical): " + ", ".join(result["degenerate"]["practical"])
    )
    return "\n".join(lines)
