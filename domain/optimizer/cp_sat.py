"""CP-SAT bed assignment (P0 snapshot) — multi-objective + constraints."""

# pyright: reportMissingImports=false, reportAttributeAccessIssue=false
# ↑ ortools type stubs incomplete — false positives, code runs fine

from __future__ import annotations

import uuid
import hashlib
import math
from typing import Mapping, Sequence

from ortools.sat.python import cp_model
from sqlalchemy import text

from infra.config import load_yaml
from infra.db import get_engine
from domain.optimizer.eval_split import split_stay_ids
from domain.optimizer.objectives import (
    OBJECTIVES,
    ModelContext,
    apply_objective,
    build_objectives,
    objective_bounds,
    zone_label as _zone_label,
)
from domain.scoring.priority import build_priority


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


def _needs_ventilator(stay_id: int) -> bool:
    """Deterministic pseudo-random: ~35% of patients need ventilator."""
    h = hashlib.md5(str(stay_id).encode()).hexdigest()
    return int(h[:8], 16) % 100 < 35


_ISO_MODES = ("none", "careunit_keyword", "real")
_ICU_UNIT_KEYWORDS = ("micu", "sicu", "cvicu", "nsicu")


def _is_icu_unit(careunit: str | None) -> bool:
    """True when the careunit name refers to a critical-care unit."""
    return any(kw in (careunit or "").lower() for kw in _ICU_UNIT_KEYWORDS)


def _resolve_iso_mode(opt: Mapping[str, object]) -> str:
    """Return the configured isolation-flag derivation mode."""
    isolation = opt.get("isolation", {}) or {}
    mode = str(isolation.get("mode", "none"))
    if mode not in _ISO_MODES:
        raise ValueError(
            f"unknown isolation.mode: {mode}; expected one of {', '.join(_ISO_MODES)}"
        )
    return mode


def _iso_flags(
    careunits: list[str | None],
    mode: str,
    real_flags: list[bool] | None = None,
) -> list[bool]:
    """Derive per-patient isolation demand.

    none             -> nobody requires isolation (C3 disabled, ISO beds ordinary)
    careunit_keyword -> legacy heuristic: any ICU unit name implies isolation
    real             -> caller-supplied flags from feat.stay_flags
    """
    if mode == "none":
        return [False] * len(careunits)
    if mode == "careunit_keyword":
        return [_is_icu_unit(cu) for cu in careunits]
    if real_flags is None:
        raise RuntimeError(
            "isolation.mode=real requires feat.stay_flags(stay_id, needs_iso)"
        )
    if len(real_flags) != len(careunits):
        raise ValueError("real_flags length mismatch")
    return [bool(v) for v in real_flags]


def _load_real_iso_flags(engine, stay_ids: list[int]) -> dict[int, bool]:
    """Load real infection flags; raises a clear error when the table is absent."""
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT stay_id, needs_iso FROM feat.stay_flags "
                    "WHERE stay_id = ANY(:ids)"
                ),
                {"ids": stay_ids},
            )
            return {int(r[0]): bool(r[1]) for r in rows}
    except Exception as exc:
        raise RuntimeError(
            "isolation.mode=real requires feat.stay_flags(stay_id, needs_iso); "
            "create the table or set isolation.mode to 'none'"
        ) from exc


_PRIORITY_MODES = ("sofa_rule", "composite")
_CANDIDATE_MODES = ("top_score", "fixed_sample", "stratified")
_VENT_MODES = ("none", "pseudo_random", "proxy_rule", "real")


def _resolve_vent_mode(opt: Mapping[str, object]) -> str:
    """Return the configured ventilator-requirement mode."""
    vent = opt.get("vent", {}) or {}
    mode = str(vent.get("mode", "none"))
    if mode not in _VENT_MODES:
        raise ValueError(
            f"unknown vent.mode: {mode}; expected one of {', '.join(_VENT_MODES)}"
        )
    return mode


def _vent_flags(
    stay_ids: list[int],
    careunits: list[str | None],
    sofa_totals: list[float],
    mode: str,
    *,
    proxy_sofa_min: float = 5.0,
    real_flags: list[bool] | None = None,
) -> list[bool]:
    """Derive per-patient ventilator demand.

    none          -> nobody requires a ventilator (C4 disabled)
    pseudo_random -> legacy MD5 heuristic (~35%), baseline only
    proxy_rule    -> constructed proxy: SOFA >= proxy_sofa_min and ICU careunit
    real          -> caller-supplied flags from feat.stay_flags
    """
    n = len(stay_ids)
    if len(careunits) != n or len(sofa_totals) != n:
        raise ValueError("vent inputs length mismatch")
    if mode == "none":
        return [False] * n
    if mode == "pseudo_random":
        return [_needs_ventilator(int(sid)) for sid in stay_ids]
    if mode == "proxy_rule":
        return [
            float(sofa) >= proxy_sofa_min and _is_icu_unit(cu)
            for sofa, cu in zip(sofa_totals, careunits)
        ]
    if real_flags is None:
        raise RuntimeError(
            "vent.mode=real requires feat.stay_flags(stay_id, needs_vent)"
        )
    if len(real_flags) != n:
        raise ValueError("real_flags length mismatch")
    return [bool(v) for v in real_flags]


def _load_real_vent_flags(engine, stay_ids: list[int]) -> dict[int, bool]:
    """Load real ventilation flags; raises a clear error when the table is absent."""
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT stay_id, needs_vent FROM feat.stay_flags "
                    "WHERE stay_id = ANY(:ids)"
                ),
                {"ids": stay_ids},
            )
            return {int(r[0]): bool(r[1]) for r in rows}
    except Exception as exc:
        raise RuntimeError(
            "vent.mode=real requires feat.stay_flags(stay_id, needs_vent); "
            "create the table or set vent.mode to 'none'"
        ) from exc


def _resolve_candidate_mode(opt: Mapping[str, object]) -> str:
    """Return how the static candidate pool is drawn."""
    cfg = opt.get("candidates", {}) or {}
    mode = str(cfg.get("mode", "top_score"))
    if mode not in _CANDIDATE_MODES:
        raise ValueError(
            f"unknown candidates.mode: {mode}; expected one of {', '.join(_CANDIDATE_MODES)}"
        )
    return mode


def _resolve_priority_mode(opt: Mapping[str, object]) -> str:
    """Return the configured priority construction mode."""
    priority = opt.get("priority", {}) or {}
    mode = str(priority.get("mode", "sofa_rule"))
    if mode not in _PRIORITY_MODES:
        raise ValueError(
            f"unknown priority.mode: {mode}; expected one of {', '.join(_PRIORITY_MODES)}"
        )
    return mode


_LAMBDA_DEFAULTS = {
    "occupancy": 2.0,
    "wait": 10.0,
    "overload": 1.0,
    "balance": 0.1,
    "zone_mismatch": 0.5,
    "move": 0.5,
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
    split: str | None = None,
    previous_beds: Mapping[int, int] | None = None,
    active_objectives: Sequence[str] | None = None,
    pivot: str | None = None,
    epsilon: Mapping[str, float] | None = None,
) -> dict:
    """Run CP-SAT bed assignment.

    Args:
        run_id: optional run identifier.
        lambda_weights: optional lambda overrides.
        persist: whether to write assignments into sched.assignments.
        split: restrict candidates to "calib" (70% tuning) or "eval" (30%
            report-only) per eval_split config. None = all candidates.
        previous_beds: optional stay_id -> bed_id map from the previous
            decision step; enables the move penalty (f5).
        active_objectives: weighted-sum objective names (default: all six).
        pivot: optimize this objective alone (anchor solve / epsilon pivot).
        epsilon: upper bounds for the non-pivot objectives; requires pivot.
    """
    if split is not None and split not in ("calib", "eval"):
        raise ValueError("split must be 'calib', 'eval' or None")
    opt = load_yaml("optimizer.yaml")
    lam = _resolve_lambda_weights(opt.get("lambda", {}), lambda_weights)
    iso_mode = _resolve_iso_mode(opt)
    vent_mode = _resolve_vent_mode(opt)
    vent_cfg = opt.get("vent", {}) or {}
    vent_proxy_sofa_min = float(vent_cfg.get("proxy_sofa_min", 5.0))
    priority_mode = _resolve_priority_mode(opt)
    if epsilon and pivot is None:
        raise ValueError("epsilon requires an explicit pivot objective")
    if pivot is not None and pivot not in OBJECTIVES:
        raise ValueError(f"unknown pivot objective: {pivot}")
    if active_objectives:
        unknown = set(active_objectives) - set(OBJECTIVES)
        if unknown:
            raise ValueError(f"unknown objective(s): {', '.join(sorted(unknown))}")
    prev_bed = {int(k): int(v) for k, v in (previous_beds or {}).items()}
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
    priority_cfg = opt.get("priority", {}) or {}
    cand_cfg = opt.get("candidates", {}) or {}
    candidate_mode = _resolve_candidate_mode(opt)
    candidate_seed = int(cand_cfg.get("seed", 42))
    candidate_size = int(cand_cfg.get("size", max_patients))
    strata = max(1, int(cand_cfg.get("strata", 4)))
    wait_source = "los_percentile"

    base_sql = """
        SELECT s.stay_id,
               COALESCE(p.priority_weight, 1.0) AS priority_weight,
               COALESCE(so.sofa_total, 0) AS sofa_total,
               s.first_careunit,
               COALESCE(s.elapsed_hours, 0) AS elapsed_hours,
               cume_dist() OVER (
                   ORDER BY COALESCE(s.elapsed_hours, 0)
               ) AS los_pct
        FROM staging.icustays_v s
        LEFT JOIN feat.patient_priority p ON s.stay_id = p.stay_id
        LEFT JOIN feat.sofa_timeseries so
               ON s.stay_id = so.stay_id AND so.hour_index = 0
    """

    with engine.connect() as conn:
        if candidate_mode == "top_score":
            if priority_mode == "composite":
                rows = conn.execute(
                    text(
                        f"""
                        SELECT * FROM ({base_sql}) t
                        ORDER BY :sofa_weight * t.sofa_total / 12.0
                               + :wait_weight * t.los_pct DESC,
                                 t.stay_id
                        LIMIT :size
                        """
                    ),
                    {
                        "sofa_weight": float(priority_cfg.get("sofa_weight", 0.6)),
                        "wait_weight": float(priority_cfg.get("wait_weight", 0.4)),
                        "size": candidate_size,
                    },
                ).mappings().all()
            else:
                rows = conn.execute(
                    text(
                        f"""
                        SELECT * FROM ({base_sql}) t
                        ORDER BY t.priority_weight DESC, t.sofa_total DESC, t.stay_id
                        LIMIT :size
                        """
                    ),
                    {"size": candidate_size},
                ).mappings().all()
        elif candidate_mode == "fixed_sample":
            rows = conn.execute(
                text(
                    f"""
                    SELECT * FROM ({base_sql}) t
                    ORDER BY md5(t.stay_id::text || :seed)
                    LIMIT :size
                    """
                ),
                {"seed": str(candidate_seed), "size": candidate_size},
            ).mappings().all()
        else:  # stratified
            per_band = max(1, candidate_size // strata)
            rows = conn.execute(
                text(
                    f"""
                    WITH base AS ({base_sql}),
                    banded AS (
                        SELECT *, ntile(:strata) OVER (ORDER BY sofa_total) AS band
                        FROM base
                    ),
                    ranked AS (
                        SELECT *, row_number() OVER (
                            PARTITION BY band ORDER BY md5(stay_id::text || :seed)
                        ) AS rn
                        FROM banded
                    )
                    SELECT stay_id, priority_weight, sofa_total, first_careunit,
                           elapsed_hours, los_pct
                    FROM ranked
                    WHERE rn <= :per_band
                    ORDER BY band, rn
                    """
                ),
                {
                    "seed": str(candidate_seed),
                    "strata": strata,
                    "per_band": per_band,
                },
            ).mappings().all()

    stays = [dict(r) for r in rows]
    if len(stays) > candidate_size:
        stays = stays[:candidate_size]

    # Elapsed ICU time as the waiting proxy, normalized by its empirical
    # percentile.  MIMIC dates are shifted per subject, so calendar-time waiting
    # cannot be reconstructed across patients.
    for s in stays:
        s["wait_norm"] = min(max(float(s.get("los_pct") or 0.0), 0.0), 1.0)
        s["wait_hours"] = max(float(s.get("elapsed_hours") or 0.0), 0.0)

    if priority_mode == "composite":
        effective = build_priority(
            "composite",
            [float(s["sofa_total"]) for s in stays],
            [float(s["wait_norm"]) for s in stays],
            priority_cfg,
        )
        for s, w in zip(stays, effective):
            s["priority_weight"] = w

    # Restrict candidates to calib / eval subset (tuning only touches calib).
    split_meta = None
    if split is not None:
        meta = split_stay_ids([int(s["stay_id"]) for s in stays])
        keep = {int(x) for x in meta[f"{split}_stay_ids"]}
        stays = [s for s in stays if int(s["stay_id"]) in keep]
        split_meta = {
            "split": split,
            "calib_ratio": meta["calib_ratio"],
            "seed": meta["seed"],
            "n_calib": meta["n_calib"],
            "n_eval": meta["n_eval"],
            "n_candidates": len(stays),
        }

    n = len(stays)
    if n == 0:
        return {
            "run_id": run_id,
            "assigned": 0,
            "n_beds": n_beds,
            "n_stays": 0,
            "lambda": lam,
            "isolation_mode": iso_mode,
            "vent_mode": vent_mode,
            "priority_mode": priority_mode,
            "wait_source": wait_source,
            "candidate_mode": candidate_mode,
            "candidate_seed": candidate_seed,
            "candidate_size": candidate_size,
            "objective_mode": "empty",
            "pivot": pivot,
            "epsilon": dict(epsilon or {}),
            "active_objectives": list(active_objectives) if active_objectives else None,
            "split": split,
            "split_meta": split_meta,
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
                "unassigned": 0,
                "high_risk_waiting": 0,
                "avg_assigned_sofa": 0.0,
                "isolation_utilization": 0.0,
                "ventilator_utilization": 0.0,
            },
        }

    # Derive patient attributes
    careunits = [s.get("first_careunit") for s in stays]
    wait_values = [float(s.get("wait_hours", 0.0)) for s in stays]
    stay_ids = [int(s["stay_id"]) for s in stays]
    sofa_totals = [float(s["sofa_total"]) for s in stays]

    iso_real_flags = None
    if iso_mode == "real":
        iso_map = _load_real_iso_flags(engine, stay_ids)
        iso_real_flags = [iso_map.get(sid, False) for sid in stay_ids]

    iso_flags = _iso_flags(careunits, iso_mode, iso_real_flags)
    iso_active = iso_mode != "none"

    vent_real_flags = None
    if vent_mode == "real":
        vent_map = _load_real_vent_flags(engine, stay_ids)
        vent_real_flags = [vent_map.get(sid, False) for sid in stay_ids]

    vent_flags = _vent_flags(
        stay_ids,
        careunits,
        sofa_totals,
        vent_mode,
        proxy_sofa_min=vent_proxy_sofa_min,
        real_flags=vent_real_flags,
    )
    vent_active = vent_mode != "none"

    patient_zones = [0] * n  # preferred zone index
    weights = [0] * n
    for idx, s in enumerate(stays):
        weights[idx] = int(float(s["priority_weight"]) * 1000)
        patient_zones[idx] = _careunit_zone(careunits[idx])

    zone_specs: list[tuple[str, list[int]]] = []
    for start, count, label in bed_zones_cfg:
        bed_ids = [b - 1 for b in range(start, start + count) if 1 <= b <= n_beds]
        if bed_ids:
            zone_specs.append((str(label), bed_ids))
    regular_beds = (
        list(range(n_beds)) if not iso_active else list(range(n_iso_beds, n_beds))
    )
    ctx = ModelContext(
        n=n,
        n_beds=n_beds,
        n_iso_beds=n_iso_beds,
        weights=weights,
        sofa_vals=[int(float(s["sofa_total"])) for s in stays],
        regular_beds=regular_beds,
        iso_flags=iso_flags,
        iso_active=iso_active,
        patient_zones=patient_zones,
        bed_zone_start=bed_zone_start,
        bed_zone_count=bed_zone_count,
        zone_specs=zone_specs,
        prev_bed=prev_bed,
        stay_ids=stay_ids,
    )

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
    #            non-isolation patients cannot use isolation beds.
    #            Disabled entirely when isolation.mode=none, so ISO beds are ordinary.
    if iso_active:
        for i in range(n):
            if iso_flags[i]:
                for b in range(n_iso_beds, n_beds):
                    model.Add(x[i, b] == 0)
            else:
                for b in range(n_iso_beds):
                    model.Add(x[i, b] == 0)

    # Ventilator limit (C4).  Assumes any bed can host a ventilator.
    if vent_active:
        vent_assigned = [
            sum(x[i, b] for b in range(n_beds))
            for i in range(n)
            if vent_flags[i]
        ]
        if vent_assigned:
            model.Add(sum(vent_assigned) <= n_vents)

    # ── 3. Objectives ─────────────────────────────────────────────
    exprs = build_objectives(model, x, ctx)
    bounds = objective_bounds(ctx)
    coefficients = {
        name: _objective_coefficient(lam[name], bounds[name]) for name in lam
    }
    objective_mode = apply_objective(
        model,
        exprs,
        ctx,
        coefficients,
        pivot=pivot,
        epsilon=epsilon,
        active=active_objectives,
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
    def _value(expr):
        return expr if isinstance(expr, int) else solver.Value(expr)

    f0_val = _value(exprs["occupancy"])
    f1_val = _value(exprs["wait"])
    f2_val = _value(exprs["overload"])
    f5_val = _value(exprs["move"])
    zone_vals = [solver.Value(zl) for zl in ctx.zone_load_vars]
    balance_dev = (max(zone_vals) - min(zone_vals)) if zone_vals else 0

    n_iso_used = sum(1 for a in assignments if a["bed_type"] == "ISO")
    n_vent_used = sum(1 for a in assignments if a["needs_vent"])
    n_zone_match = sum(1 for a in assignments if a.get("zone_match"))
    zone_mismatch_val = _value(exprs["zone_mismatch"])
    high_risk_total = sum(1 for s in stays if float(s["sofa_total"]) >= 10)
    high_risk_assigned = sum(1 for a in assignments if float(a["sofa_total"]) >= 10)
    assigned_priority_total = sum(float(a["priority_weight"]) for a in assignments)
    assigned_sofa_total = sum(float(a["sofa_total"]) for a in assignments)
    assigned_count = len(assignments)

    return {
        "run_id": run_id,
        "assigned": len(assignments),
        "n_beds": n_beds,
        "n_stays": n,
        "solver_status": "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
        "lambda": lam,
        "isolation_mode": iso_mode,
        "n_iso_required": sum(iso_flags),
        "vent_mode": vent_mode,
        "n_vent_required": sum(vent_flags),
        "priority_mode": priority_mode,
        "wait_source": wait_source,
        "candidate_mode": candidate_mode,
        "candidate_seed": candidate_seed,
        "candidate_size": candidate_size,
        "objective_mode": objective_mode["mode"],
        "pivot": pivot,
        "epsilon": dict(epsilon or {}),
        "active_objectives": objective_mode.get("active"),
        "split": split,
        "split_meta": split_meta,
        "objective_scaling": {
            "bounds": bounds,
            "coefficients": coefficients,
        },
        "objective": {
            "f0_occupancy": f0_val,
            "f1_priority_total": f1_val,
            "f2_overload_penalty": f2_val,
            "f3_balance_deviation": balance_dev,
            "f4_zone_mismatch": zone_mismatch_val,
            "f5_move": f5_val,
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
            "avg_wait_hours": round(sum(wait_values) / n, 2) if n else 0.0,
            "max_wait_hours": round(max(wait_values), 2) if wait_values else 0.0,
            # ── business metrics (lambda-independent, clinical meaning) ──
            "unassigned": n - assigned_count,
            "moved_patients": f5_val,
            "high_risk_waiting": max(high_risk_total - high_risk_assigned, 0),
            "avg_assigned_sofa": round(
                assigned_sofa_total / assigned_count, 4
            ) if assigned_count else 0.0,
            "isolation_utilization": round(
                n_iso_used / n_iso_beds, 4
            ) if n_iso_beds else 0.0,
            "ventilator_utilization": round(
                n_vent_used / n_vents, 4
            ) if n_vents else 0.0,
        },
        "resources": {
            "isolation_beds_used": f"{n_iso_used}/{n_iso_beds}",
            "ventilators_used": f"{n_vent_used}/{n_vents}",
            "zone_matches": f"{n_zone_match}/{len(assignments)}",
        },
        "top_assignments": assignments,
    }

