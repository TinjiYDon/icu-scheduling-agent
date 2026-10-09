"""Unit tests for H3 L4 loaders (no DB / no PPO)."""

from __future__ import annotations

import json

from application.h3_ui import load_comparison_table


def test_load_comparison_missing(tmp_path):
    out = load_comparison_table(tmp_path)
    assert out["status"] == "missing"


def test_load_policy_comparison_json(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    payload = {
        "status": "ok",
        "fair_pool": True,
        "rows": [{"policy": "cp_sat", "assigned": 4}],
    }
    (reports / "policy_comparison.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    out = load_comparison_table(tmp_path)
    assert out["status"] == "ok"
    assert out["payload"]["rows"][0]["assigned"] == 4


def test_load_raw_ppo_evaluation_flattens(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    raw = {
        "fair_pool": True,
        "ppo": {"assigned": 4, "n_stays": 20},
        "greedy": {"assigned": 4, "n_stays": 20},
        "cp_sat": {"assigned": 4, "n_stays": 20, "evaluation": {}},
    }
    (reports / "ppo_evaluation.json").write_text(json.dumps(raw), encoding="utf-8")
    out = load_comparison_table(tmp_path)
    assert out["status"] == "ok"
    assert len(out["payload"]["rows"]) == 3
