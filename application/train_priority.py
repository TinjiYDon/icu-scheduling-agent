"""CLI: rebuild feat.patient_priority via in-repo GBDT; print arrival intensity."""

from __future__ import annotations

import argparse
import json

from domain.scoring.predict_priority import build_priority_from_gbdt, estimate_arrival_intensity


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--no-los-feature", action="store_true")
    p.add_argument("--intensity-only", action="store_true")
    args = p.parse_args()
    if args.intensity_only:
        print(json.dumps(estimate_arrival_intensity(), ensure_ascii=False, indent=2))
        return
    out = build_priority_from_gbdt(use_los_feature=not args.no_los_feature)
    intensity = estimate_arrival_intensity()
    print(json.dumps({"priority": out, "intensity": intensity}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
