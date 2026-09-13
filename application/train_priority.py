"""CLI: rebuild feat.patient_priority via in-repo GBDT; print arrival intensity."""

from __future__ import annotations

import argparse
import json

from domain.scoring.predict_priority import build_priority_from_gbdt, estimate_arrival_intensity


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--no-los-feature", action="store_true")
    p.add_argument("--intensity-only", action="store_true")
    p.add_argument(
        "--write-rolling",
        action="store_true",
        help="also write suggested rates into configs/optimizer.yaml rolling.*",
    )
    args = p.parse_args()
    if args.intensity_only:
        intensity = estimate_arrival_intensity()
        print(json.dumps(intensity, ensure_ascii=False, indent=2))
        if args.write_rolling:
            from application.write_rolling_rates import write_rolling_rates

            print(json.dumps(write_rolling_rates(), ensure_ascii=False, indent=2))
        return
    out = build_priority_from_gbdt(use_los_feature=not args.no_los_feature)
    intensity = estimate_arrival_intensity()
    payload: dict = {"priority": out, "intensity": intensity}
    if args.write_rolling:
        from application.write_rolling_rates import write_rolling_rates

        payload["rolling_write"] = write_rolling_rates()
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
