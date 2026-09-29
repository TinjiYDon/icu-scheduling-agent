"""CLI: S2-MOO phase 4 six-scenario lightweight method pack."""

from __future__ import annotations

import argparse
import json
from functools import partial

from sqlalchemy import text

from domain.optimizer.cp_sat import run_assignment
from domain.optimizer.eval_split import split_stay_ids
from domain.optimizer.moo_scenarios import (
    ScenarioSpec,
    list_scenarios,
    run_all_scenarios,
    summarize_for_status,
    write_scenario_reports,
)
from infra.config import load_yaml
from infra.db import get_engine


def _resolve_pool(spec: ScenarioSpec, split: str | None) -> list[int] | None:
    """Build scenario-specific stay_id pools from Layer1."""
    opt = load_yaml("optimizer.yaml")
    cap = int(spec.pool_cap)
    engine = get_engine()
    with engine.connect() as conn:
        if spec.pool == "high_sofa":
            rows = conn.execute(
                text(
                    """
                    SELECT s.stay_id
                    FROM staging.icustays s
                    JOIN feat.sofa_timeseries so
                      ON s.stay_id = so.stay_id AND so.hour_index = 0
                    WHERE so.sofa_total >= :sofa_min
                    ORDER BY so.sofa_total DESC, s.stay_id
                    LIMIT :cap
                    """
                ),
                {"sofa_min": float(spec.sofa_min or 8), "cap": cap},
            ).fetchall()
        elif spec.pool == "zone_skew":
            kw = f"%{spec.careunit_keyword or 'MICU'}%"
            rows = conn.execute(
                text(
                    """
                    SELECT s.stay_id
                    FROM staging.icustays s
                    WHERE s.first_careunit ILIKE :kw
                    ORDER BY s.stay_id
                    LIMIT :cap
                    """
                ),
                {"kw": kw, "cap": cap},
            ).fetchall()
        else:
            return None

    stay_ids = [int(r[0]) for r in rows]
    if split in ("calib", "eval") and stay_ids:
        ratio = float((opt.get("eval_split") or {}).get("calib_ratio", 0.7))
        seed = int((opt.get("eval_split") or {}).get("seed", 42))
        parts = split_stay_ids(stay_ids, calib_ratio=ratio, seed=seed)
        return list(
            parts["calib_stay_ids"] if split == "calib" else parts["eval_stay_ids"]
        )
    return stay_ids


def main() -> None:
    p = argparse.ArgumentParser(description="S2-MOO phase 4 six-scenario pack")
    p.add_argument("--split", default="calib", choices=["calib", "eval", "all"])
    p.add_argument("--max-time", type=float, default=30.0)
    p.add_argument("--skip-epsilon", action="store_true")
    p.add_argument(
        "--only",
        default="",
        help="comma-separated scenario ids (default=all)",
    )
    args = p.parse_args()

    split = None if args.split == "all" else args.split
    specs = list_scenarios()
    if args.only.strip():
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        specs = [s for s in specs if s.id in wanted]

    solve = partial(run_assignment, max_time_seconds=args.max_time)

    def _progress(sid: str, phase: str) -> None:
        print(json.dumps({"scenario": sid, "phase": phase}, ensure_ascii=False), flush=True)

    payload = run_all_scenarios(
        solve,
        resolve_pool=_resolve_pool,
        scenarios=specs,
        split=split,
        persist=False,
        max_time_seconds=args.max_time,
        include_epsilon=not args.skip_epsilon,
        progress=_progress,
    )
    paths = write_scenario_reports(payload)
    summary = summarize_for_status(payload)
    print(
        json.dumps(
            {"n_rows": len(payload["rows"]), "summary": summary, "paths": paths},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
