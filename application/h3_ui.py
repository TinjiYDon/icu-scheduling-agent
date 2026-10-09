"""L4: H3 fair policy comparison for Streamlit."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from domain.ops.policy_comparison import flatten_comparison

ROOT = Path(__file__).resolve().parents[1]
TABLE_PATH = ROOT / "reports" / "policy_comparison.json"
RAW_PATH = ROOT / "reports" / "ppo_evaluation.json"


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


def run_h3_compare(*, write_table: bool = True) -> dict[str, Any]:
    """Run fair evaluate_ppo and optionally write policy_comparison.json."""
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
