"""Raw observations -> causal SOFA -> real CP-SAT rolling decisions."""

from domain.rolling.timed_pareto import run_timed_pareto
from domain.scoring.sofa_full import compute_snapshot


def test_delayed_lab_reaches_solver_only_when_available():
    start = "2150-01-01 00:00:00"
    events = [
        {
            "table": "labevents",
            "itemid": 50912,
            "valuenum": 1.0,
            "valueuom": "mg/dL",
            "charttime": "2150-01-01 23:00:00",
            "storetime": "2150-01-01 23:30:00",
        },
        {
            "table": "labevents",
            "itemid": 50912,
            "valuenum": 6.0,
            "valueuom": "mg/dL",
            "charttime": "2150-01-01 23:30:00",
            "storetime": "2150-01-02 01:00:00",
        },
    ]
    payload = {
        "stays": [{"stay_id": 1, "first_careunit": "MICU"}],
        "scores": [compute_snapshot(1, start, hour, events) for hour in (24, 26)],
    }
    report = run_timed_pareto(
        payload,
        sample_size=1,
        n_beds=1,
        n_steps=1,
        admission_rate=0,
        discharge_rate=0,
        max_time_seconds=3,
    )
    first, second = report["history"]
    assert first["scores"][0]["sofa_total"] == 0
    assert second["scores"][0]["sofa_total"] == 4
    assert first["objective_values"]["wait"] == 1000
    assert second["objective_values"]["wait"] == 1400
    assert second["predecision_beds"] == first["assignments"]
    assert all(row["patient_conservation"] for row in report["history"])
