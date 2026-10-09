"""Unit tests for S2-MOO L4 loaders (no solver / no DB)."""

from __future__ import annotations

import json

from application.moo_ui import (
    flatten_front,
    load_phase3_summary,
    load_scenarios_latest,
    rows_to_csv,
    scenario_wide_table,
)


def test_load_missing_reports(tmp_path):
    s = load_phase3_summary(tmp_path)
    c = load_scenarios_latest(tmp_path)
    assert s["status"] == "missing"
    assert c["status"] == "missing"


def test_load_and_wide_table(tmp_path):
    moo = tmp_path / "reports" / "moo"
    moo.mkdir(parents=True)
    (moo / "summary_latest.json").write_text(
        json.dumps(
            {
                "scan": {"n_grid": 81, "hypervolume": 0.03},
                "front": [{"source": "a", "values": {"wait": 10, "high_risk": 4}}],
            }
        ),
        encoding="utf-8",
    )
    (moo / "scenarios_latest.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "scenario_id": "S1",
                        "scenario_name": "正常",
                        "method": "weighted_sum",
                        "status": "OPTIMAL",
                        "assigned": 20,
                        "obj_wait": 1,
                        "obj_high_risk": 4,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    s = load_phase3_summary(tmp_path)
    c = load_scenarios_latest(tmp_path)
    assert s["status"] == "ok"
    assert s["payload"]["scan"]["n_grid"] == 81
    wide = scenario_wide_table(c["payload"])
    assert wide[0]["weighted_sum_assigned"] == 20
    front = flatten_front(s["payload"]["front"])
    assert front[0]["wait"] == 10
    assert "wait" in rows_to_csv(front)
