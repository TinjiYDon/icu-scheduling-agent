from __future__ import annotations

import json

import pytest

from domain.optimizer.objectives import OBJECTIVES
from domain.optimizer.pareto import save_anchors, solve_anchors


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, *args, **kwargs):
        return _FakeResult(self._rows)


class _FakeEngine:
    def __init__(self, rows):
        self._rows = rows

    def connect(self):
        return _FakeConn(self._rows)


def _candidate_rows(n=100):
    return [
        {
            "stay_id": i,
            "priority_weight": 2.0,
            "sofa_total": 5.0,
            "first_careunit": "MICU",
        }
        for i in range(1, n + 1)
    ]


def _fake_opt_config():
    return {
        "lambda": {"wait": 10.0, "overload": 1.0, "balance": 0.1, "zone_mismatch": 0.5},
        "resources": {
            "n_beds": 20,
            "n_isolation_beds": 4,
            "n_ventilators": 8,
            "max_patients": 200,
            "bed_zones": [
                [1, 4, "ISO"],
                [5, 4, "MICU"],
                [9, 4, "SICU"],
                [13, 4, "CCU"],
                [17, 4, "NICU"],
            ],
        },
        "eval_split": {"calib_ratio": 0.7, "seed": 42},
    }


@pytest.fixture
def fake_db(monkeypatch):
    monkeypatch.setattr(
        "domain.optimizer.cp_sat.load_yaml", lambda name: _fake_opt_config()
    )
    monkeypatch.setattr(
        "domain.optimizer.cp_sat.get_engine", lambda: _FakeEngine(_candidate_rows(100))
    )


def test_solve_anchors_produces_pure_and_practical(fake_db):
    out = solve_anchors(practical_guard_ratio=0.9)

    assert set(out["pure"]) == set(OBJECTIVES)
    assert set(out["practical"]) == set(OBJECTIVES)
    assert out["ideal"]["occupancy"] == 20
    assert out["ideal"]["wait"] == 40000
    assert out["pure"]["overload"]["objectives"]["occupancy"] == 0

    guard = out["guard"]["occupancy_min"]
    assert guard == 18
    for name in OBJECTIVES:
        if name == "occupancy":
            continue
        assert out["practical"][name]["objectives"]["occupancy"] >= guard


def test_payoff_table_covers_all_anchors(fake_db):
    out = solve_anchors(practical_guard_ratio=0.5)

    assert out["guard"]["occupancy_min"] == 10
    assert set(out["payoff_table"]) == set(OBJECTIVES)
    for name in OBJECTIVES:
        assert set(out["payoff_table"][name]) == set(OBJECTIVES)


def test_save_anchors_writes_json(fake_db, tmp_path):
    out = solve_anchors(practical_guard_ratio=0.9)
    path = save_anchors(out, tmp_path / "anchors.json")

    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["run_id"] == out["run_id"]
    assert "ideal" in payload and "practical_ideal" in payload
