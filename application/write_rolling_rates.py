"""Write MIMIC-calibrated rolling rates into configs/optimizer.yaml."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from domain.scoring.predict_priority import estimate_arrival_intensity

ROOT = Path(__file__).resolve().parents[1]
OPT_PATH = ROOT / "configs" / "optimizer.yaml"


def write_rolling_rates(*, dry_run: bool = False) -> dict:
    intensity = estimate_arrival_intensity()
    adm = float(intensity["suggested_admission_rate"])
    dis = float(intensity["suggested_discharge_rate"])
    raw = OPT_PATH.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) or {}
    rolling = dict(data.get("rolling") or {})
    before = {
        "admission_rate": rolling.get("admission_rate"),
        "discharge_rate": rolling.get("discharge_rate"),
    }
    rolling["admission_rate"] = adm
    rolling["discharge_rate"] = dis
    if "step_hours" not in rolling:
        rolling["step_hours"] = int(intensity.get("step_hours", 2))
    data["rolling"] = rolling
    if not dry_run:
        OPT_PATH.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
    return {
        "status": "ok",
        "path": str(OPT_PATH),
        "before": before,
        "after": {"admission_rate": adm, "discharge_rate": dis},
        "intensity": intensity,
        "dry_run": dry_run,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Calibrate rolling.* from MIMIC LOS")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    import json

    print(json.dumps(write_rolling_rates(dry_run=args.dry_run), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
