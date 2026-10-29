"""CLI H5: Predict-then-Optimize decision ablation on a fair stay pool."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from domain.ops.h3_fair import resource_overrides_from_env, stay_ids_from_env
from domain.ops.pto_decision_ablation import (
    assignment_set,
    build_priority_maps,
    decision_delta,
    pto_takeaways,
)
from domain.scoring.predict_priority import _careunit_code, _fit_gbdt, _load_training_frame
from infra.config import load_yaml
from infra.db import get_engine

ROOT = Path(__file__).resolve().parents[1]
OUT_DEFAULT = ROOT / "reports" / "pto_decision_ablation.json"


def _mo_values(result: dict[str, Any]) -> dict[str, Any]:
    values = dict((result.get("multiobjective") or {}).get("values") or {})
    ev = result.get("evaluation") or {}
    return {
        "assigned": result.get("assigned"),
        "status": result.get("solver_status"),
        "occupancy": values.get("occupancy", result.get("assigned")),
        "high_risk": values.get("high_risk"),
        "wait": values.get("wait"),
        "overload": values.get("overload"),
        "high_risk_waiting": ev.get("high_risk_waiting"),
        "avg_assigned_sofa": ev.get("avg_assigned_sofa"),
        "priority_total": ev.get("priority_total"),
    }


def _load_maps_for_pool(stay_ids: list[int]) -> dict[str, dict[int, float]]:
    engine = get_engine()
    with engine.connect() as conn:
        rows = _load_training_frame(conn)
    by_id = {int(r["stay_id"]): r for r in rows}
    pool_rows = [by_id[s] for s in stay_ids if s in by_id]
    if not pool_rows:
        pool_rows = [
            {
                "stay_id": s,
                "sofa_total": 0.0,
                "los_hours": 0.0,
                "first_careunit": "",
            }
            for s in stay_ids
        ]

    vocab: dict[str, int] = {}
    X_list: list[list[float]] = []
    y_list: list[float] = []
    ids: list[int] = []
    for r in rows:
        sofa = float(r["sofa_total"] or 0.0)
        los = float(r["los_hours"] or 0.0)
        cu = _careunit_code(str(r["first_careunit"] or ""), vocab)
        X_list.append([sofa, float(cu), los])
        y_list.append(1.0 + sofa / 10.0 + 2.0 / (1.0 + max(los, 1.0)))
        ids.append(int(r["stay_id"]))
    X = np.asarray(X_list, dtype=float)
    y = np.asarray(y_list, dtype=float)
    _, model = _fit_gbdt(X, y)
    pred = np.clip(np.asarray(model.predict(X), dtype=float), 1.0, 5.0)
    gbdt_preds = {sid: float(p) for sid, p in zip(ids, pred)}
    return build_priority_maps(pool_rows, gbdt_preds=gbdt_preds)


def run_pto_ablation(
    *,
    candidate_patients: int | None = None,
    max_time_seconds: float = 30.0,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    from domain.optimizer.cp_sat import run_assignment
    from domain.rl.factory import build_icu_env

    opt = load_yaml("optimizer.yaml")
    n_cand = int(
        candidate_patients
        if candidate_patients is not None
        else (opt.get("ppo") or {}).get("candidate_patients", 40)
    )

    env0 = build_icu_env()
    stay_ids = stay_ids_from_env(env0)[:n_cand]
    if not stay_ids:
        raise RuntimeError("empty stay pool — restore Layer1 dump first")
    env = build_icu_env(candidate_stay_ids=stay_ids)
    resources = resource_overrides_from_env(env)
    maps = _load_maps_for_pool(stay_ids)

    rows: list[dict[str, Any]] = []
    sets: dict[str, frozenset[int]] = {}
    for name, overrides in maps.items():
        result = run_assignment(
            persist=False,
            stay_ids=stay_ids,
            resource_overrides=resources,
            priority_overrides=overrides,
            max_time_seconds=max_time_seconds,
            objective_mode="weighted_sum",
        )
        metrics = _mo_values(result)
        metrics["method"] = name
        rows.append(metrics)
        sets[name] = assignment_set(result)

    deltas = decision_delta(sets, reference="formula")
    report = {
        "status": "ok",
        "hypothesis": "H5",
        "fair_pool": True,
        "n_stays": len(stay_ids),
        "shared_resources": resources,
        "shared_stay_ids": stay_ids,
        "rows": rows,
        "assignment_delta": deltas,
        "takeaways": pto_takeaways(rows, deltas),
        "note": (
            "Predict-then-optimize decision ablation: same beds/constraints, "
            "swap urgency model via priority_overrides. No decision risk_score."
        ),
    }
    out = Path(output_path) if output_path else OUT_DEFAULT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["path"] = str(out)
    return report


def main() -> None:
    p = argparse.ArgumentParser(description="H5 PtO 决策质量消融")
    p.add_argument("--candidate-patients", type=int, default=40)
    p.add_argument("--max-time", type=float, default=30.0)
    p.add_argument("--out", default=str(OUT_DEFAULT))
    args = p.parse_args()
    print(
        json.dumps(
            run_pto_ablation(
                candidate_patients=args.candidate_patients,
                max_time_seconds=args.max_time,
                output_path=args.out,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
