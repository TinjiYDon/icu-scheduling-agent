"""CP-SAT bed assignment (P0 snapshot) — multi-objective + constraints."""

# pyright: reportMissingImports=false, reportAttributeAccessIssue=false
# ↑ ortools type stubs incomplete — false positives, code runs fine

from __future__ import annotations

import uuid
import hashlib
import math
from typing import Mapping

from ortools.sat.python import cp_model
from sqlalchemy import text

from infra.config import load_yaml
from infra.db import get_engine


def _careunit_zone(careunit: str | None) -> int:
    """Map careunit to bed zone index. 0=unknown, 1=MICU, 2=SICU, 3=CCU, 4=NICU."""
    if not careunit:
        return 0
    cu = careunit.lower()
    if any(kw in cu for kw in ("micu",)):
        return 1
    if any(kw in cu for kw in ("sicu", "tsicu")):
        return 2
    if any(kw in cu for kw in ("ccu", "cvicu")):
        return 3
    if any(kw in cu for kw in ("nicu", "nsicu")):
        return 4
    return 0


def _zone_label(zone_idx: int) -> str:
    return ["UNK", "MICU", "SICU", "CCU", "NICU"][zone_idx] if 0 <= zone_idx <= 4 else "UNK"


def _needs_ventilator(stay_id: int) -> bool:
    """Deterministic pseudo-random: ~35% of patients need ventilator."""
    h = hashlib.md5(str(stay_id).encode()).hexdigest()
    return int(h[:8], 16) % 100 < 35


_LAMBDA_DEFAULTS = {
    "wait": 10.0,
    "overload": 1.0,
    "balance": 0.1,
    "zone_mismatch": 0.5,
}


def _resolve_lambda_weights(
    configured: Mapping[str, object] | None,
    overrides: Mapping[str, float] | None = None,
) -> dict[str, float]:
    """Merge and validate objective weights used by CP-SAT experiments."""
    weights = dict(_LAMBDA_DEFAULTS)
    if configured:
        unknown = set(configured) - set(weights)
        if unknown:
            raise ValueError(f"unknown lambda weight(s): {', '.join(sorted(unknown))}")
        weights.update(configured)
    if overrides:
        unknown = set(overrides) - set(weights)
        if unknown:
            raise ValueError(f"unknown lambda weight(s): {', '.join(sorted(unknown))}")
        weights.update(overrides)

    resolved: dict[str, float] = {}
    for name, raw_value in weights.items():
        value = float(raw_value)
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"lambda.{name} must be a finite non-negative number")
        resolved[name] = value
    if not any(resolved.values()):
        raise ValueError("at least one lambda weight must be greater than zero")
    return resolved


def _objective_coefficient(
    weight: float, upper_bound: int = 1, scale: int = 1_000_000
) -> int:
    """Normalize an objective to a shared integer scale for CP-SAT.

    The raw objectives have very different magnitudes (priority is stored at
    x1000 while balance is usually single digits).  Dividing the common scale
    by each objective's upper bound makes lambda values represent relative
    preference instead of accidental unit size.
    """
    if weight == 0:
        return 0
    return max(1, round(weight * scale / max(int(upper_bound), 1)))


def run_assignment(
    run_id: str | None = None,
    lambda_weights: Mapping[str, float] | None = None,
    *,
    persist: bool = True,
) -> dict:
    opt = load_yaml("optimizer.yaml")
    lam = _resolve_lambda_weights(opt.get("lambda", {}), lambda_weights)
    n_beds = int(opt.get("resources", {}).get("n_beds", 20))
    n_iso_beds = int(opt.get("resources", {}).get("n_isolation_beds", 4))
    n_vents = int(opt.get("resources", {}).get("n_ventilators", 8))
    max_patients = int(opt.get("resources", {}).get("max_patients", n_beds * 10))
    bed_zones_cfg = opt.get("resources", {}).get(
        "bed_zones",
        [[1, 4, "ISO"], [5, 4, "MICU"], [9, 4, "SICU"], [13, 4, "CCU"], [17, 4, "NICU"]],
    )
    # Build bed_id → zone_label lookup (bed_id is 1-indexed)
    bed_zone_label: dict[int, str] = {}
    bed_zone_start: dict[str, int] = {}
    bed_zone_count: dict[str, int] = {}
    for start, count, label in bed_zones_cfg:
        for b in range(start, start + count):
            bed_zone_label[b] = label
        bed_zone_start[label] = start
        bed_zone_count[label] = count
    run_id = run_id or f"p0_{uuid.uuid4().hex[:8]}"

    # ── 1. Load patients ──────────────────────────────────────────
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT s.stay_id, COALESCE(p.priority_weight, 1.0) AS priority_weight,
                       COALESCE(so.sofa_total, 0) AS sofa_total,
                       s.first_careunit
                FROM staging.icustays s
                LEFT JOIN feat.patient_priority p ON s.stay_id = p.stay_id
                LEFT JOIN feat.sofa_timeseries so ON s.stay_id = so.stay_id AND so.hour_index = 0
                ORDER BY priority_weight DESC, sofa_total DESC
                LIMIT :max_patients
                """
            ),
            {"max_patients": max_patients},
        ).mappings().all()

    stays = [dict(r) for r in rows]
    n = len(stays)
    if n == 0:
        return {
            "run_id": run_id,
            "assigned": 0,
            "n_beds": n_beds,
            "n_stays": 0,
            "lambda": lam,
            "status": "empty",
            "evaluation": {
                "assignment_rate": 0.0,
                "priority_total": 0.0,
                "avg_assigned_priority": 0.0,
                "high_risk_assigned_rate": 1.0,
                "overload_penalty": 0,
                "balance_deviation": 0,
                "zone_match_rate": 0.0,
                "solve_time_seconds": 0.0,
            },
        }

    # Derive patient attributes
    iso_flags = [False] * n
    vent_flags = [False] * n
    patient_zones = [0] * n  # preferred zone index
    weights = [0] * n
    for idx, s in enumerate(stays):
        weights[idx] = int(float(s["priority_weight"]) * 1000)
        cu = s.get("first_careunit")
        iso_flags[idx] = any(kw in (cu or "").lower() for kw in ("micu", "sicu", "cvicu", "nsicu"))
        vent_flags[idx] = _needs_ventilator(s["stay_id"])
        patient_zones[idx] = _careunit_zone(cu)

    # ── 2. Build CP-SAT model ─────────────────────────────────────
    model = cp_model.CpModel()
    x: dict[tuple[int, int], cp_model.IntVar] = {}

    for i in range(n):
        for b in range(n_beds):
            x[i, b] = model.NewBoolVar(f"x_{i}_{b}")

    # Hard constraints: each bed ≤1 patient, each patient ≤1 bed
    for b in range(n_beds):
        model.Add(sum(x[i, b] for i in range(n)) <= 1)
    for i in range(n):
        model.Add(sum(x[i, b] for b in range(n_beds)) <= 1)

    # Isolation: isolation patients can only use isolation beds (first n_iso_beds)
    #            non-isolation patients cannot use isolation beds
    for i in range(n):
        if iso_flags[i]:
            for b in range(n_iso_beds, n_beds):
                model.Add(x[i, b] == 0)
        else:
            for b in range(n_iso_beds):
                model.Add(x[i, b] == 0)

    # Ventilator limit
    vent_assigned = []
    for i in range(n):
        if vent_flags[i]:
            vent_assigned.append(sum(x[i, b] for b in range(n_beds)))
    if vent_assigned:
        model.Add(sum(vent_assigned) <= n_vents)

    # ── 3. Multi-objective ────────────────────────────────────────
    # f₁: maximize priority_weight (minimize wait for high-risk patients)
    f1 = sum(weights[i] * x[i, b] for i in range(n) for b in range(n_beds))

    # f₂: overload penalty — penalize assigning high-sofa patients to regular beds
    sofa_vals = [int(float(s["sofa_total"])) for s in stays]
    overload_penalty = sum(
        sofa_vals[i] * x[i, b] for i in range(n) for b in range(n_iso_beds, n_beds)
    )

    # f₃: balance — minimize max deviation across 4 bed zones
    zone_size = max(1, n_beds // 4)
    zone_load_vars = []
    for z in range(4):
        start = z * zone_size
        end = start + zone_size if z < 3 else n_beds
        zl = model.NewIntVar(0, zone_size, f"zone_load_{z}")
        model.Add(zl == sum(x[i, b] for i in range(n) for b in range(start, end)))
        zone_load_vars.append(zl)

    # Minimize the maximum deviation from the mean load
    max_dev = model.NewIntVar(0, n_beds, "max_dev")
    avg_target = n_beds // 4
    for zl in zone_load_vars:
        dev = model.NewIntVar(0, n_beds, f"dev_{z}")
        model.Add(dev >= zl - avg_target)
        model.Add(dev >= avg_target - zl)
        model.Add(max_dev >= dev)

    # f₄: zone mismatch penalty — penalize assigning patient to non-preferred zone
    #      Isolation patients in ISO beds are always a match (no penalty)
    zone_mismatch_penalty = model.NewIntVar(0, n_beds * 100, "zone_mismatch")
    mismatch_terms = []
    for i in range(n):
        pz = patient_zones[i]
        if pz <= 0:
            continue
        pref_label = _zone_label(pz)
        pref_start = bed_zone_start.get(pref_label)
        pref_count = bed_zone_count.get(pref_label, 0)
        if pref_start is None or pref_label == "ISO":
            continue

        in_pref_zone = sum(x[i, b - 1] for b in range(pref_start, pref_start + pref_count))
        assigned_anywhere = sum(x[i, b] for b in range(n_beds))
        in_iso = sum(x[i, b] for b in range(n_iso_beds))

        # Mismatch only if: assigned somewhere AND NOT in pref zone AND NOT in ISO
        mismatch = model.NewIntVar(0, 1, f"mismatch_{i}")
        model.Add(mismatch >= assigned_anywhere - in_pref_zone - in_iso)
        mismatch_terms.append(mismatch)

    if mismatch_terms:
        model.Add(zone_mismatch_penalty == sum(mismatch_terms))
    else:
        model.Add(zone_mismatch_penalty == 0)

    # Combined objective
    objective_bounds = {
        "wait": max(1, n_beds * max(weights, default=1)),
        "overload": max(1, n_beds * max(sofa_vals, default=1)),
        "balance": max(1, n_beds),
        "zone_mismatch": max(1, n_beds),
    }
    objective_coefficients = {
        name: _objective_coefficient(lam[name], objective_bounds[name])
        for name in lam
    }
    model.Maximize(
        objective_coefficients["wait"] * f1
        - objective_coefficients["overload"] * overload_penalty
        - objective_coefficients["balance"] * max_dev
        - objective_coefficients["zone_mismatch"] * zone_mismatch_penalty
    )

    # ── 4. Solve ──────────────────────────────────────────────────
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(f"CP-SAT failed: status={status}")

    # ── 5. Collect results ────────────────────────────────────────
    assignments = []
    for i in range(n):
        for b in range(n_beds):
            if solver.Value(x[i, b]) == 1:
                bid = b + 1
                zone_lbl = bed_zone_label.get(bid, "REG")
                is_match = (
                    (zone_lbl == _zone_label(patient_zones[i]))
                    or (zone_lbl == "ISO" and iso_flags[i])
                )
                assignments.append({
                    "stay_id": stays[i]["stay_id"],
                    "bed_id": bid,
                    "bed_type": zone_lbl,
                    "patient_zone": _zone_label(patient_zones[i]),
                    "zone_match": is_match,
                    "priority_weight": stays[i]["priority_weight"],
                    "sofa_total": stays[i]["sofa_total"],
                    "needs_iso": iso_flags[i],
                    "needs_vent": vent_flags[i],
                })

    # Tuning runs should not fill the production assignment table.
    if persist:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM sched.assignments WHERE run_id = :run_id"),
                {"run_id": run_id},
            )
            for a in assignments:
                conn.execute(
                    text(
                        "INSERT INTO sched.assignments (run_id, stay_id, bed_id) "
                        "VALUES (:run_id, :stay_id, :bed_id)"
                    ),
                    {
                        "run_id": run_id,
                        "stay_id": a["stay_id"],
                        "bed_id": a["bed_id"],
                    },
                )

    # ── 6. Explainable output ─────────────────────────────────────
    f1_val = sum(
        weights[i] * solver.Value(x[i, b]) for i in range(n) for b in range(n_beds)
    )
    f2_val = sum(
        sofa_vals[i] * solver.Value(x[i, b])
        for i in range(n)
        for b in range(n_iso_beds, n_beds)
    )
    zone_vals = [solver.Value(zl) for zl in zone_load_vars]
    balance_dev = solver.Value(max_dev)

    n_iso_used = sum(1 for a in assignments if a["bed_type"] == "ISO")
    n_vent_used = sum(1 for a in assignments if a["needs_vent"])
    n_zone_match = sum(1 for a in assignments if a.get("zone_match"))
    zone_mismatch_val = solver.Value(zone_mismatch_penalty)
    high_risk_total = sum(1 for s in stays if float(s["sofa_total"]) >= 10)
    high_risk_assigned = sum(1 for a in assignments if float(a["sofa_total"]) >= 10)
    assigned_priority_total = sum(float(a["priority_weight"]) for a in assignments)
    assigned_count = len(assignments)

    return {
        "run_id": run_id,
        "assigned": len(assignments),
        "n_beds": n_beds,
        "n_stays": n,
        "solver_status": "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
        "lambda": lam,
        "objective_scaling": {
            "bounds": objective_bounds,
            "coefficients": objective_coefficients,
        },
        "objective": {
            "f1_priority_total": f1_val,
            "f2_overload_penalty": f2_val,
            "f3_balance_deviation": balance_dev,
            "f4_zone_mismatch": zone_mismatch_val,
            "zone_loads": zone_vals,
        },
        # These business metrics are independent of lambda coefficients, so
        # results from different tuning runs can be compared directly.
        "evaluation": {
            "assignment_rate": round(assigned_count / n, 4),
            "priority_total": round(assigned_priority_total, 4),
            "avg_assigned_priority": round(
                assigned_priority_total / assigned_count, 4
            ) if assigned_count else 0.0,
            "high_risk_assigned_rate": round(
                high_risk_assigned / high_risk_total, 4
            ) if high_risk_total else 1.0,
            "overload_penalty": f2_val,
            "balance_deviation": balance_dev,
            "zone_match_rate": round(
                n_zone_match / assigned_count, 4
            ) if assigned_count else 0.0,
            "solve_time_seconds": round(solver.WallTime(), 4),
        },
        "resources": {
            "isolation_beds_used": f"{n_iso_used}/{n_iso_beds}",
            "ventilators_used": f"{n_vent_used}/{n_vents}",
            "zone_matches": f"{n_zone_match}/{len(assignments)}",
        },
        "top_assignments": assignments,
    }

