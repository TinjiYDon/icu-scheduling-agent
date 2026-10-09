"""CLI: same-pool bake-off — greedy vs Weighted / Lex / ε-mid CP-SAT (no PPO required)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from domain.ops.h3_fair import resource_overrides_from_env, stay_ids_from_env
from domain.ops.method_bakeoff import (
    bakeoff_takeaways,
    epsilon_bounds_from_reference,
    flatten_bakeoff_row,
)
from domain.optimizer.moo_phase3 import DEFAULT_OBJECTIVES, DEFAULT_PRIMARY
from infra.config import load_yaml

ROOT = Path(__file__).resolve().parents[1]
OUT_DEFAULT = ROOT / "reports" / "method_bakeoff_latest.json"


def _mo_values(result: dict[str, Any]) -> dict[str, int]:
    values = dict((result.get("multiobjective") or {}).get("values") or {})
    out: dict[str, int] = {}
    for k in DEFAULT_OBJECTIVES:
        try:
            out[k] = int(values.get(k, 0) or 0)
        except (TypeError, ValueError):
            out[k] = 0
    return out


def run_method_bakeoff(
    *,
    split: str | None = "calib",
    max_time_seconds: float = 30.0,
    candidate_patients: int | None = None,
    persist: bool = False,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Fair pool: greedy + three CP-SAT mechanisms share stay_ids and resources."""
    from application.evaluate_ppo import _cp_sat_canonical, _enrich_policy_metrics
    from domain.optimizer.cp_sat import run_assignment
    from domain.rl.evaluation import evaluate_greedy
    from domain.rl.factory import build_icu_env

    opt = load_yaml("optimizer.yaml")
    ppo = opt.get("ppo") or {}
    n_cand = int(
        candidate_patients
        if candidate_patients is not None
        else ppo.get("candidate_patients", 20)
    )

    # Build one env to freeze the fair pool (same stays + bed layout).
    env0 = build_icu_env()
    # Prefer explicit stay list from env; truncate to candidate size for greedy parity.
    stay_ids = stay_ids_from_env(env0)[:n_cand]
    if not stay_ids:
        raise RuntimeError("empty stay pool — restore Layer1 dump first")

    env = build_icu_env(candidate_stay_ids=stay_ids)
    resources = resource_overrides_from_env(env)
    n_beds = int(resources["n_beds"])
    seed = int(ppo.get("seed", 42))

    rows: list[dict[str, Any]] = []

    # --- greedy (sequential heuristic on same ICUEnv) ---
    try:
        g_env = build_icu_env(candidate_stay_ids=stay_ids, n_beds=n_beds)
        g_raw = _enrich_policy_metrics(
            g_env, evaluate_greedy(g_env, seed=seed)
        )
        rows.append(
            {
                "method": "greedy",
                "status": "ok",
                "assigned": g_raw.get("assigned"),
                "n_stays": g_raw.get("n_stays") or len(stay_ids),
                "wall_time_seconds": None,
                "high_risk_wait": g_raw.get("high_risk_wait"),
                "constraint_violations": g_raw.get("constraint_violations"),
                "values": {
                    "occupancy": g_raw.get("assigned"),
                    "high_risk": None,
                    "wait": None,
                    "overload": None,
                },
                "exact_hierarchy": None,
            }
        )
    except Exception as exc:  # noqa: BLE001
        rows.append(
            {
                "method": "greedy",
                "status": f"ERROR:{type(exc).__name__}",
                "assigned": None,
                "n_stays": len(stay_ids),
                "values": {},
                "error": str(exc),
            }
        )

    def _append_cp(label: str, **kwargs: Any) -> dict[str, Any]:
        try:
            result = run_assignment(
                persist=persist,
                stay_ids=stay_ids,
                resource_overrides=resources,
                max_time_seconds=max_time_seconds,
                **kwargs,
            )
            mo = result.get("multiobjective") or {}
            ev = _cp_sat_canonical(result.get("evaluation") or {})
            row = {
                "method": label,
                "status": result.get("solver_status"),
                "assigned": result.get("assigned"),
                "n_stays": result.get("n_stays") or len(stay_ids),
                "wall_time_seconds": mo.get("wall_time_seconds"),
                "high_risk_wait": ev.get("high_risk_wait"),
                "constraint_violations": ev.get("constraint_violations"),
                "values": _mo_values(result),
                "exact_hierarchy": mo.get("exact_hierarchy"),
            }
        except Exception as exc:  # noqa: BLE001
            row = {
                "method": label,
                "status": f"ERROR:{type(exc).__name__}",
                "assigned": None,
                "n_stays": len(stay_ids),
                "values": {},
                "error": str(exc),
            }
        rows.append(row)
        return row

    # --- WS then Lex; ε bounds derived from WS so mid-grid stays pool-feasible ---
    ws_row = _append_cp("weighted_sum", objective_mode="weighted_sum")
    _append_cp(
        "lexicographic",
        objective_mode="lexicographic",
        objective_order=list(DEFAULT_OBJECTIVES),
    )
    eps_bounds = epsilon_bounds_from_reference(ws_row.get("values"))
    _append_cp(
        "epsilon_mid",
        objective_mode="epsilon_constraint",
        epsilon_primary=DEFAULT_PRIMARY,
        epsilon_bounds=eps_bounds,
    )

    table = [flatten_bakeoff_row(r) for r in rows]
    report = {
        "status": "ok",
        "fair_pool": True,
        "split_hint": split,
        "n_stays": len(stay_ids),
        "shared_n_beds": n_beds,
        "shared_resources": resources,
        "shared_stay_ids": stay_ids,
        "epsilon_bounds": eps_bounds,
        "epsilon_bounds_note": "Derived from weighted_sum values (half max / 1.5× min), not fixed defaults.",
        "rows": table,
        "takeaways": bakeoff_takeaways(rows),
        "note": (
            "Method bake-off on one fair pool (same stay_ids + bed layout). "
            "Offline CP-SAT/greedy only — do not claim online MIMIC-PPO. "
            "Innovation claim is multi-objective mechanism contrast, not 'we used OR-Tools'."
        ),
    }

    out = Path(output_path) if output_path else OUT_DEFAULT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["path"] = str(out)
    return report


def main() -> None:
    p = argparse.ArgumentParser(description="同池方法 bake-off（贪心 / WS / Lex / ε）")
    p.add_argument("--split", default="calib", help="文档口径；本入口用 stay_ids 显式池")
    p.add_argument("--max-time", type=float, default=30.0)
    p.add_argument("--candidate-patients", type=int, default=None)
    p.add_argument("--out", default=str(OUT_DEFAULT))
    args = p.parse_args()
    report = run_method_bakeoff(
        split=None if args.split == "all" else args.split,
        max_time_seconds=float(args.max_time),
        candidate_patients=args.candidate_patients,
        output_path=args.out,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
