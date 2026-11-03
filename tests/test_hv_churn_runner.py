"""Wiring test for the HV–churn engineering runner (no DB, no solver)."""
from __future__ import annotations

import numpy as np

from application import run_hv_churn as runner
from domain.optimizer.pareto_io import FrontSnapshot


def _fake_rolling(**_kwargs):
    return {
        "total_steps": 2,
        "final_occupancy": 20,
        "bed_utilization_pct": 100.0,
        "history": [
            {
                "step": 0,
                "occupied": 20,
                "admitted": 0,
                "discharged": 0,
                "assignments": {"1": "1", "2": "2"},
                "candidate_ids": [1, 2],
            },
            {
                "step": 1,
                "occupied": 20,
                "admitted": 2,
                "discharged": 2,
                "assignments": {"1": "1", "2": "3"},
                "candidate_ids": [1, 2],
            },
        ],
    }


def _fake_front(snapshot, **_kwargs):
    # 每个 snap 给两行归一化前沿
    return FrontSnapshot(
        step=int(snapshot["step"]),
        ids=["a", "b"],
        points=np.asarray([[1.0, 0.5], [0.5, 1.0]], dtype=float),
    )


def test_runner_wires_fronts_to_hv_churn(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "run_rolling_simulation", _fake_rolling)
    monkeypatch.setattr(runner, "_front_for_snapshot", _fake_front)
    out = tmp_path / "hv.json"
    report = runner.run_hv_churn(n_steps=2, levels=2, max_time=1.0, output_path=out)
    assert report["status"] == "ok"
    assert len(report["series"]) == 2
    assert report["summary"]["n_steps"] == 2
    assert report["series"][0]["step"] == 0
    assert out.is_file()
