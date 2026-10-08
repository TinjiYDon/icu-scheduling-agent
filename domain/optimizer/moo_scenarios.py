"""S2-MOO phase 4: six stress scenarios × lightweight method pack.

Each scenario fixes resources and/or candidate pool, then runs Weighted Sum,
Lexicographic, and one epsilon-constraint point under the same time budget.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from domain.optimizer.moo_epsilon_recal import DEFAULT_EPSILON_BOUNDS as RECAL_DEFAULT_EPS
from domain.optimizer.moo_epsilon_recal import scenario_epsilon_bounds
from domain.optimizer.moo_phase3 import DEFAULT_OBJECTIVES, OBJECTIVE_SENSES
from domain.optimizer.resources import scale_bed_layout

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "moo"

# Mid-grid epsilon from phase-3 A2 payoff (loose–tight midpoint-ish).
DEFAULT_EPSILON_BOUNDS: dict[str, int] = dict(RECAL_DEFAULT_EPS)


@dataclass(frozen=True)
class ScenarioSpec:
    id: str
    name: str
    description: str
    resource_overrides: dict[str, Any] = field(default_factory=dict)
    pool: str = "default"  # default | high_sofa | zone_skew
    sofa_min: float | None = None
    careunit_keyword: str | None = None
    pool_cap: int = 200


SCENARIOS: tuple[ScenarioSpec, ...] = (
    ScenarioSpec(
        id="S1_normal",
        name="正常容量",
        description="默认 20 床 / 4 隔离 / 8 呼吸机",
    ),
    ScenarioSpec(
        id="S2_bed_shortage",
        name="总床位不足",
        description="n_beds=12，按比例缩放分区",
        resource_overrides=scale_bed_layout(12),
    ),
    ScenarioSpec(
        id="S3_iso_shortage",
        name="隔离床不足",
        description="n_isolation_beds=1，其余默认",
        resource_overrides={"n_isolation_beds": 1},
    ),
    ScenarioSpec(
        id="S4_vent_shortage",
        name="呼吸机不足",
        description="n_ventilators=2",
        resource_overrides={"n_ventilators": 2},
    ),
    ScenarioSpec(
        id="S5_high_sofa",
        name="高 SOFA 集中",
        description="候选池优先 SOFA≥8",
        pool="high_sofa",
        sofa_min=8.0,
        pool_cap=200,
    ),
    ScenarioSpec(
        id="S6_zone_skew",
        name="科室需求不均衡",
        description="候选池偏向 MICU careunit",
        pool="zone_skew",
        careunit_keyword="MICU",
        pool_cap=200,
    ),
)


SolveFn = Callable[..., dict[str, Any]]
PoolFn = Callable[[ScenarioSpec, str | None], list[int] | None]


def list_scenarios() -> list[ScenarioSpec]:
    return list(SCENARIOS)


def _extract_row(result: dict[str, Any], *, scenario: ScenarioSpec, method: str) -> dict[str, Any]:
    values = dict((result.get("multiobjective") or {}).get("values") or {})
    ev = dict(result.get("evaluation") or {})
    return {
        "scenario_id": scenario.id,
        "scenario_name": scenario.name,
        "method": method,
        "status": result.get("solver_status") or result.get("status") or "UNKNOWN",
        "assigned": result.get("assigned"),
        "n_beds": result.get("n_beds"),
        "n_stays": result.get("n_stays"),
        "wall_time_seconds": float(
            ((result.get("multiobjective") or {}).get("wall_time_seconds"))
            or ev.get("solve_time_seconds")
            or 0.0
        ),
        "exact_hierarchy": ((result.get("multiobjective") or {}).get("exact_hierarchy")),
        "assignment_rate": ev.get("assignment_rate"),
        "high_risk_waiting": ev.get("high_risk_waiting"),
        "zone_match_rate": ev.get("zone_match_rate"),
        "isolation_utilization": ev.get("isolation_utilization"),
        "ventilator_utilization": ev.get("ventilator_utilization"),
        **{f"obj_{k}": values.get(k) for k in DEFAULT_OBJECTIVES},
        "error": result.get("error"),
    }


def run_scenario_pack(
    solve: SolveFn,
    *,
    scenario: ScenarioSpec,
    split: str | None = "calib",
    persist: bool = False,
    max_time_seconds: float = 30.0,
    epsilon_bounds: Mapping[str, int] | None = None,
    stay_ids: list[int] | None = None,
    include_epsilon: bool = True,
) -> list[dict[str, Any]]:
    """Run WS + Lex (+ optional one ε) for a single scenario."""
    common: dict[str, Any] = {
        "persist": persist,
        "split": split if stay_ids is None else None,
        "stay_ids": stay_ids,
        "resource_overrides": dict(scenario.resource_overrides) or None,
        "max_time_seconds": max_time_seconds,
    }
    # drop None resource_overrides for cleaner kwargs
    if common["resource_overrides"] is None:
        common.pop("resource_overrides")
    if stay_ids is None:
        common.pop("stay_ids", None)
    else:
        common.pop("split", None)

    rows: list[dict[str, Any]] = []
    methods: list[tuple[str, dict[str, Any]]] = [
        ("weighted_sum", {"objective_mode": "weighted_sum"}),
        (
            "lexicographic",
            {
                "objective_mode": "lexicographic",
                "objective_order": list(DEFAULT_OBJECTIVES),
            },
        ),
    ]
    if include_epsilon:
        methods.append(
            (
                "epsilon_mid",
                {
                    "objective_mode": "epsilon_constraint",
                    "epsilon_primary": "wait",
                    "epsilon_bounds": dict(epsilon_bounds or DEFAULT_EPSILON_BOUNDS),
                },
            )
        )

    for method, kwargs in methods:
        try:
            result = solve(**common, **kwargs)
        except Exception as exc:  # noqa: BLE001
            result = {
                "solver_status": f"ERROR:{type(exc).__name__}",
                "error": str(exc),
                "assigned": None,
                "n_beds": (scenario.resource_overrides or {}).get("n_beds"),
                "multiobjective": {"values": {}, "wall_time_seconds": 0.0},
                "evaluation": {},
            }
        rows.append(_extract_row(result, scenario=scenario, method=method))
    return rows


def run_all_scenarios(
    solve: SolveFn,
    *,
    resolve_pool: PoolFn | None = None,
    scenarios: Sequence[ScenarioSpec] | None = None,
    split: str | None = "calib",
    persist: bool = False,
    max_time_seconds: float = 30.0,
    epsilon_bounds: Mapping[str, int] | None = None,
    include_epsilon: bool = True,
    progress: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    specs = list(scenarios or SCENARIOS)
    all_rows: list[dict[str, Any]] = []
    for spec in specs:
        stay_ids = None
        if resolve_pool is not None and spec.pool != "default":
            stay_ids = resolve_pool(spec, split)
        if progress:
            progress(spec.id, "start")
        per_eps = (
            dict(epsilon_bounds)
            if epsilon_bounds is not None
            else scenario_epsilon_bounds(spec)
        )
        rows = run_scenario_pack(
            solve,
            scenario=spec,
            split=split,
            persist=persist,
            max_time_seconds=max_time_seconds,
            epsilon_bounds=per_eps,
            stay_ids=stay_ids,
            include_epsilon=include_epsilon,
        )
        for row in rows:
            row["epsilon_bounds_used"] = dict(per_eps)
        all_rows.extend(rows)
        if progress:
            progress(spec.id, "done")

    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "split": split,
        "max_time_seconds": max_time_seconds,
        "epsilon_bounds": dict(epsilon_bounds) if epsilon_bounds is not None else "per_scenario",
        "epsilon_recal": True,
        "objective_senses": dict(OBJECTIVE_SENSES),
        "scenarios": [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "resource_overrides": s.resource_overrides,
                "pool": s.pool,
            }
            for s in specs
        ],
        "rows": all_rows,
    }


def write_scenario_reports(
    payload: Mapping[str, Any],
    *,
    out_dir: Path | None = None,
    stamp: str | None = None,
) -> dict[str, str]:
    directory = out_dir or REPORT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    ts = stamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    paths = {
        "summary": str(directory / f"scenarios_{ts}.json"),
        "csv": str(directory / f"scenarios_{ts}.csv"),
        "latest": str(directory / "scenarios_latest.json"),
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    Path(paths["summary"]).write_text(text, encoding="utf-8")
    Path(paths["latest"]).write_text(text, encoding="utf-8")

    rows = list(payload.get("rows") or [])
    if rows:
        fieldnames = list(rows[0].keys())
        with Path(paths["csv"]).open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    return paths


def summarize_for_status(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """One compact row per scenario using lexicographic as primary display."""
    by_sc: dict[str, dict[str, Any]] = {}
    for row in payload.get("rows") or []:
        sid = str(row.get("scenario_id"))
        by_sc.setdefault(sid, {"scenario_id": sid, "scenario_name": row.get("scenario_name")})
        method = str(row.get("method"))
        by_sc[sid][method] = {
            "status": row.get("status"),
            "assigned": row.get("assigned"),
            "wait": row.get("obj_wait"),
            "high_risk": row.get("obj_high_risk"),
            "overload": row.get("obj_overload"),
            "high_risk_waiting": row.get("high_risk_waiting"),
            "wall_time_seconds": row.get("wall_time_seconds"),
        }
    return list(by_sc.values())
