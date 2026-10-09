"""CLI H6: rolling CP-SAT reoptimize vs greedy-admit-only (same seed schedule)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from domain.ops.rolling_contrast import (
    rolling_contrast_takeaways,
    summarize_rolling_run,
)
from domain.rolling.engine import run_rolling_simulation

ROOT = Path(__file__).resolve().parents[1]
OUT_DEFAULT = ROOT / "reports" / "rolling_contrast.json"


def run_rolling_contrast(
    *,
    n_steps: int = 12,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    rolling = run_rolling_simulation(n_steps=n_steps, reoptimize=True)
    static = run_rolling_simulation(n_steps=n_steps, reoptimize=False)
    sum_r = summarize_rolling_run(rolling)
    sum_s = summarize_rolling_run(static)
    report = {
        "status": "ok",
        "hypothesis": "H6",
        "n_steps": n_steps,
        "rolling_reoptimize": sum_r,
        "greedy_admit_only": sum_s,
        "takeaways": rolling_contrast_takeaways(sum_r, sum_s),
        "note": (
            "Same discharge/admission RNG schedule; only differ on per-step "
            "CP-SAT reoptimize. Offline simulation — not a clinical trial."
        ),
    }
    out = Path(output_path) if output_path else OUT_DEFAULT
    out.parent.mkdir(parents=True, exist_ok=True)
    # Drop bulky history from disk summary (keep metrics only)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["path"] = str(out)
    return report


def main() -> None:
    p = argparse.ArgumentParser(description="H6 滚动再优化 vs 贪心填床")
    p.add_argument("--steps", type=int, default=12)
    p.add_argument("--out", default=str(OUT_DEFAULT))
    args = p.parse_args()
    print(
        json.dumps(
            run_rolling_contrast(n_steps=args.steps, output_path=args.out),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
