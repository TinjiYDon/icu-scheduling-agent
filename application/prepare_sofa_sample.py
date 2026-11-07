"""Prepare reproducible, causal six-component SOFA from the local MIMIC ZIP."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import timedelta
from pathlib import Path

from data_access.mimic_sample import extract_sample, load_cached_events
from domain.scoring.sofa_full import COMPONENTS, compute_snapshot, timestamp


def score_cache(cache: Path, output: Path, *, hours: int = 48, step: int = 2) -> dict:
    manifest = json.loads((cache / "manifest.json").read_text(encoding="utf-8"))
    if hours > manifest["config"]["max_hours"]:
        raise ValueError("requested scoring range exceeds extracted cache range")
    events = load_cached_events(cache)
    scores = []
    for s in manifest["stays"]:
        t0, t1 = timestamp(s["intime"]), timestamp(s["outtime"])
        for hour in range(0, hours + 1, step):
            if t0 + timedelta(hours=hour) > t1:
                break
            scores.append(
                compute_snapshot(s["stay_id"], t0, hour, events.get(s["stay_id"], []))
            )
    observed = Counter(
        k for row in scores for k in COMPONENTS if row["components"][k] is not None
    )
    at24 = [r for r in scores if r["hour_index"] == 24]
    report = {
        "schema_version": 1,
        "source": "local MIMIC-IV ZIP selected raw events",
        "config": dict(
            manifest["config"],
            step_hours=step,
            score_hours=hours,
            missing_total_policy="zero contribution with explicit missing mask",
            priority_source="sofa_rule: 1 + sofa_total / 10",
            time_axis="hours since each individual ICU admission",
        ),
        "stays": manifest["stays"],
        "scores": scores,
        "coverage": {
            "n_stays": len(manifest["stays"]),
            "n_scores": len(scores),
            "observed_scores_per_component": dict(observed),
            "hour24_complete": sum(not r["missing_components"] for r in at24),
            "hour24_n": len(at24),
            "quality_flags": dict(
                Counter(f for r in scores for f in r["quality_flags"])
            ),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {"output": str(output.resolve()), "coverage": report["coverage"]}, indent=2
        ),
        flush=True,
    )
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--zip", type=Path, default=Path("../mimic-iv-3.1.zip"))
    p.add_argument("--cache", type=Path, default=Path("artifacts/sofa_sample"))
    p.add_argument(
        "--out", type=Path, default=Path("artifacts/sofa_sample/sofa_sample.json")
    )
    p.add_argument("--size", type=int, default=50)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--min-stay-hours", type=int, default=48)
    p.add_argument("--hours", type=int, default=48)
    p.add_argument("--step", type=int, default=2)
    p.add_argument("--chunksize", type=int, default=500_000)
    p.add_argument("--extract-only", action="store_true")
    p.add_argument("--score-only", action="store_true")
    args = p.parse_args()
    if args.step < 1 or args.hours < 0 or args.chunksize < 1:
        p.error("step/chunksize must be positive and hours nonnegative")
    if args.extract_only and args.score_only:
        p.error("--extract-only and --score-only are mutually exclusive")
    if not args.score_only:
        extract_sample(
            args.zip,
            args.cache,
            size=args.size,
            seed=args.seed,
            min_stay_hours=args.min_stay_hours,
            max_hours=args.hours,
            chunksize=args.chunksize,
        )
    if not args.extract_only:
        score_cache(args.cache, args.out, hours=args.hours, step=args.step)


if __name__ == "__main__":
    main()
