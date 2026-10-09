"""L4: H3 fair policy comparison for Streamlit."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from domain.ops.policy_comparison import flatten_comparison

ROOT = Path(__file__).resolve().parents[1]
TABLE_PATH = ROOT / "reports" / "policy_comparison.json"
RAW_PATH = ROOT / "reports" / "ppo_evaluation.json"
BENCHMARK_PATH = ROOT / "reports" / "ppo_benchmark.json"


def _model_present(model_path: str | Path | None = None) -> bool:
    raw = Path(model_path or "artifacts/ppo_icu")
    if not raw.is_absolute():
        raw = ROOT / raw
    return raw.exists() or Path(str(raw) + ".zip").exists()


def load_comparison_table(root: Path | None = None) -> dict[str, Any]:
    """Load flattened H3 table from reports (missing → status=missing)."""
    base = root or ROOT
    table = base / "reports" / "policy_comparison.json"
    raw = base / "reports" / "ppo_evaluation.json"
    if table.is_file():
        try:
            payload = json.loads(table.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {"status": "error", "error": str(exc), "payload": None}
        return {"status": "ok", "path": str(table), "payload": payload}
    if raw.is_file():
        try:
            report = json.loads(raw.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {"status": "error", "error": str(exc), "payload": None}
        if "rows" in report:
            return {"status": "ok", "path": str(raw), "payload": report}
        return {
            "status": "ok",
            "path": str(raw),
            "payload": flatten_comparison(report),
        }
    return {"status": "missing", "path": str(table), "payload": None}


def load_benchmark(root: Path | None = None) -> dict[str, Any]:
    """Load multi-episode S3 deepen report."""
    base = root or ROOT
    path = base / "reports" / "ppo_benchmark.json"
    if not path.is_file():
        return {"status": "missing", "path": str(path), "payload": None}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "error", "error": str(exc), "path": str(path), "payload": None}
    return {"status": "ok", "path": str(path), "payload": payload}


def benchmark_summary_rows(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Flatten summary means into a small table for Streamlit."""
    if not payload:
        return []
    summary = payload.get("summary") or {}
    rows: list[dict[str, Any]] = []
    for policy in ("ppo", "greedy", "cp_sat"):
        block = summary.get(policy) or {}
        rows.append(
            {
                "policy": policy,
                "mean_assigned": block.get("mean_assigned"),
                "mean_total_reward": block.get("mean_total_reward"),
                "mean_high_risk_wait": block.get("mean_high_risk_wait"),
                "mean_constraint_violations": block.get("mean_constraint_violations"),
            }
        )
    return rows


def run_h3_compare(*, write_table: bool = True) -> dict[str, Any]:
    """Run fair evaluate_ppo and optionally write policy_comparison.json."""
    if not _model_present():
        raise FileNotFoundError(
            "缺少 PPO 检查点 artifacts/ppo_icu(.zip)。离线对照需要模型文件（不入 Git）。"
        )
    from application.evaluate_ppo import evaluate_ppo

    report = evaluate_ppo()
    flat = report.get("comparison_table") or flatten_comparison(report)
    path: str | None = None
    if write_table:
        TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        TABLE_PATH.write_text(
            json.dumps(flat, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        path = str(TABLE_PATH)
    return {
        "status": "ok",
        "path": path,
        "payload": flat,
        "fair_pool": bool(report.get("fair_pool")),
        "shared_resources": report.get("shared_resources"),
        "note": report.get("note"),
    }


def run_h3_benchmark(
    *,
    episodes: int = 3,
    write_report: bool = True,
) -> dict[str, Any]:
    """Run multi-episode fair benchmark (S3 deepen)."""
    if not _model_present():
        raise FileNotFoundError(
            "缺少 PPO 检查点 artifacts/ppo_icu(.zip)。多 episode 深化需要模型文件（不入 Git）。"
        )
    from application.evaluate_ppo_benchmark import evaluate_ppo_benchmark

    out_path = str(BENCHMARK_PATH) if write_report else None
    report = evaluate_ppo_benchmark(episodes=episodes, output_path=out_path)
    return {
        "status": "ok",
        "path": out_path,
        "payload": report,
        "fair_pool": bool(report.get("fair_pool")),
        "shared_resources": report.get("shared_resources"),
        "note": (report.get("summary") or {}).get("note") or report.get("note"),
        "rows": benchmark_summary_rows(report),
    }
