"""Regression coverage for rolling conservation, resource limits and solver failures."""

import random

import pytest

from domain.optimizer import cp_sat
from domain.rolling import engine


class FakeConnection:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def connect(self):
        return self

    def execute(self, *args, **kwargs):
        return self

    def mappings(self):
        return self

    def all(self):
        return self.rows


@pytest.fixture
def setup_simulation(monkeypatch):
    config = {
        "resources": {"n_beds": 2, "n_isolation_beds": 1, "n_ventilators": 1,
                      "bed_zones": [[1, 1, "ISO"], [2, 1, "REG"]]},
        "rolling": {"step_hours": 2},
    }
    monkeypatch.setattr(engine, "load_yaml", lambda _: config)
    monkeypatch.setattr(engine, "needs_isolation", lambda cu: cu == "ISO")
    monkeypatch.setattr(engine, "needs_ventilator", lambda sid, sofa: sofa >= 10)

    def setup(rows, results):
        monkeypatch.setattr(engine, "get_engine", lambda: FakeConnection(rows))
        calls = []
        outputs = iter(results)

        def solve(**kwargs):
            calls.append(kwargs)
            result = next(outputs)
            if isinstance(result, Exception):
                raise result
            return {"solver_status": "OPTIMAL", "top_assignments": result}

        monkeypatch.setattr(cp_sat, "run_assignment", solve)
        return calls

    return setup


def patient(sid, weight=1, sofa=0, careunit="REG"):
    return {"stay_id": sid, "w": weight, "sofa": sofa, "first_careunit": careunit}


def assignment(sid, bed):
    return {"stay_id": sid, "bed_id": bed}


def test_zero_rates_preserve_patients_and_do_not_reseed_global_rng(setup_simulation):
    calls = setup_simulation(
        [patient(1), patient(2)],
        [[assignment(1, 1)], [assignment(1, 1)], [assignment(1, 1)]],
    )
    rng_state = random.getstate()
    result = engine.run_rolling_simulation(
        n_steps=2, discharge_rate=0, admission_rate=0, persist=False,
    )
    assert random.getstate() == rng_state
    assert result["total_discharges"] == 0
    assert result["total_admissions"] == 1
    assert result["final_occupancy"] == 1
    assert all(c["max_new_admissions"] == 0 for c in calls[1:])
    assert all(c["stay_ids"] == [1] for c in calls[1:])
    assert all(c["persist"] is False for c in calls)


def test_displaced_patient_returns_to_queue_and_can_be_selected_again(setup_simulation):
    calls = setup_simulation(
        [patient(1, 3), patient(2, 2), patient(3, 1)],
        [[assignment(1, 1)], [assignment(2, 2)], [assignment(1, 1)]],
    )
    result = engine.run_rolling_simulation(
        n_steps=2, discharge_rate=0, admission_rate=0.5, persist=False, retain_occupied=False,
    )
    assert 1 in calls[2]["stay_ids"]
    assert result["history"][1]["returned_to_queue_stay_ids"] == [1]
    assert result["history"][1]["admitted_stay_ids"] == [2]
    assert result["total_returns_to_queue"] == 2
    assert result["total_admissions"] == 3
    assert result["final_occupancy"] == 1
    assert result["history"][-1]["waiting"] == 2
    assert result["total_admissions"] - result["total_returns_to_queue"] == result["final_occupancy"]


def test_greedy_skips_patients_without_legal_isolation_or_ventilator_capacity(setup_simulation):
    setup_simulation(
        [patient(1, 4, 12), patient(2, 3, 12, "ISO"), patient(3, 2, 12), patient(4, 1)],
        [[assignment(1, 1)]],
    )
    result = engine.run_rolling_simulation(
        n_steps=1, discharge_rate=0, admission_rate=1, reoptimize=False, persist=False,
    )
    final = result["history"][-1]
    assert final["admitted_stay_ids"] == [4]
    assert {a["stay_id"] for a in final["assignments"]} == {1, 4}
    assert final["constraint_violation"] is False
    assert final["waiting"] == 2


def test_solver_timeout_preserves_last_valid_survivors(setup_simulation):
    setup_simulation(
        [patient(1), patient(2)],
        [[assignment(1, 1)], RuntimeError("CP-SAT failed: status=UNKNOWN")],
    )
    result = engine.run_rolling_simulation(
        n_steps=1, discharge_rate=0, admission_rate=1, persist=False,
    )
    assert result["final_occupancy"] == 1
    assert result["history"][-1]["solver_status"] == "FALLBACK"
    assert result["history"][-1]["admitted"] == 0
    assert result["solver_failures"] == 1


@pytest.mark.parametrize("invalid", [
    [assignment(1, 2)],  # Isolation demand on a regular bed.
    [assignment(1, 1), assignment(1, 2)],
    [assignment(1, 1), assignment(2, 1)],
    [assignment(1, 3)],
])
def test_invalid_solver_output_is_rejected(setup_simulation, invalid):
    setup_simulation([patient(1, sofa=12, careunit="ISO"), patient(2)], [invalid])
    with pytest.raises(RuntimeError, match="invalid rolling assignment"):
        engine.run_rolling_simulation(n_steps=0, persist=False)


@pytest.mark.parametrize("kwargs", [
    {"n_steps": -1}, {"n_steps": 1.5}, {"admission_rate": -0.1},
    {"discharge_rate": 1.1}, {"discharge_rate": float("nan")},
])
def test_invalid_simulation_parameters_fail_before_database_access(setup_simulation, kwargs):
    with pytest.raises(ValueError):
        engine.run_rolling_simulation(**kwargs)


def test_cp_sat_honors_zero_new_admission_limit(monkeypatch):
    config = {"resources": {"n_beds": 2, "n_isolation_beds": 1, "n_ventilators": 2,
                            "bed_zones": [[1, 1, "ISO"], [2, 1, "REG"]]}}
    rows = [{"stay_id": sid, "priority_weight": sid, "sofa_total": 0,
             "first_careunit": "REG"} for sid in (1, 2, 3)]
    monkeypatch.setattr(cp_sat, "load_yaml", lambda _: config)
    monkeypatch.setattr(cp_sat, "get_engine", lambda: FakeConnection(rows))
    result = cp_sat.run_assignment(
        persist=False, stay_ids=[1, 2, 3], occupied_beds={1: 1},
        max_new_admissions=0, max_time_seconds=5,
    )
    assert {a["stay_id"] for a in result["top_assignments"]} == {1}


def test_shared_initial_state_avoids_another_solver_call(setup_simulation):
    calls = setup_simulation([patient(1)], [])
    result = engine.run_rolling_simulation(
        n_steps=0, persist=False, initial_assignments=[assignment(1, 1)],
    )
    assert calls == []
    assert result["history"][0]["solver_status"] == "SHARED_INITIAL"
    assert result["history"][0]["assignments"][0]["stay_id"] == 1


def test_solver_cannot_remove_inpatient_without_discharge(setup_simulation):
    setup_simulation([patient(1)], [[assignment(1, 1)], []])
    with pytest.raises(RuntimeError, match="current inpatient was removed"):
        engine.run_rolling_simulation(n_steps=1, discharge_rate=0, admission_rate=0, persist=False)


def test_actual_solver_keeps_high_acuity_inpatient_at_zero_turnover(monkeypatch):
    rows = [
        {**patient(sid, 1, sofa), "priority_weight": 1, "sofa_total": sofa}
        for sid, sofa in [(1, 10), (2, 12)]
    ]
    config = {
        "lambda": {"occupancy": 1, "wait": 0.1, "overload": 1.2,
                   "balance": 0, "zone_mismatch": 0, "move": 0.5},
        "resources": {"n_beds": 1, "n_isolation_beds": 0, "n_ventilators": 1,
                      "bed_zones": [[1, 1, "REG"]]},
    }
    monkeypatch.setattr(engine, "load_yaml", lambda _: config)
    monkeypatch.setattr(cp_sat, "load_yaml", lambda _: config)
    monkeypatch.setattr(engine, "get_engine", lambda: FakeConnection(rows))
    monkeypatch.setattr(cp_sat, "get_engine", lambda: FakeConnection(rows))
    result = engine.run_rolling_simulation(
        n_steps=1, discharge_rate=0, admission_rate=0, persist=False,
        initial_assignments=[assignment(1, 1)], max_time_seconds=5,
    )
    assert result["final_occupancy"] == 1
    assert result["history"][-1]["assignments"][0]["stay_id"] == 1
    assert result["total_admissions"] == 1
    assert result["total_discharges"] == result["total_returns_to_queue"] == 0
