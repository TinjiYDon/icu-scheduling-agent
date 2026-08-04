"""Tests for CP-SAT calib/eval split restriction (no real DB required)."""

import pytest

from domain.optimizer.cp_sat import run_assignment


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
        params = kwargs or (args[1] if len(args) > 1 else {})
        stay_ids = params.get("stay_ids") if isinstance(params, dict) else None
        if stay_ids is None:
            return _FakeResult(self._rows)
        allowed = {int(stay_id) for stay_id in stay_ids}
        return _FakeResult([row for row in self._rows if row["stay_id"] in allowed])


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


def test_split_invalid_value_raises(fake_db):
    with pytest.raises(ValueError, match="split must be"):
        run_assignment(split="foo")


def test_split_none_uses_all_candidates(fake_db):
    out = run_assignment(split=None, persist=False)
    assert out["n_stays"] == 100
    assert out["split"] is None
    assert out["split_meta"] is None


def test_stay_ids_filter_limits_candidates(fake_db):
    out = run_assignment(stay_ids=[3, 5, 7], persist=False)

    assert out["n_stays"] == 3
    assert {row["stay_id"] for row in out["top_assignments"]}.issubset({3, 5, 7})


def test_split_calib_eval_disjoint_and_meta(fake_db):
    calib = run_assignment(split="calib", persist=False)
    ev = run_assignment(split="eval", persist=False)

    assert calib["split"] == "calib"
    assert ev["split"] == "eval"
    assert calib["split_meta"]["calib_ratio"] == 0.7
    assert calib["split_meta"]["seed"] == 42
    assert calib["split_meta"]["n_calib"] + calib["split_meta"]["n_eval"] == 100

    calib_ids = {a["stay_id"] for a in calib["top_assignments"]}
    eval_ids = {a["stay_id"] for a in ev["top_assignments"]}
    assert calib_ids.isdisjoint(eval_ids)


def test_evaluation_has_business_metrics(fake_db):
    """Task #4: evaluation exposes clinical business metrics, lambda-independent."""
    out = run_assignment(split=None, persist=False)
    ev = out["evaluation"]

    for key in (
        "unassigned",
        "high_risk_waiting",
        "avg_assigned_sofa",
        "isolation_utilization",
        "ventilator_utilization",
    ):
        assert key in ev, f"missing evaluation key: {key}"

    # unassigned + assigned == candidates (self-consistency)
    assert ev["unassigned"] == out["n_stays"] - out["assigned"]
    assert 0.0 <= ev["high_risk_waiting"] <= out["n_stays"]
    # utilization rates must be in [0, 1]
    assert 0.0 <= ev["isolation_utilization"] <= 1.0
    assert 0.0 <= ev["ventilator_utilization"] <= 1.0
    # avg assigned sofa is non-negative
    assert ev["avg_assigned_sofa"] >= 0.0
