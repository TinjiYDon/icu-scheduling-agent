"""Temporal causality, stable solve context, and patient conservation (no DB)."""

from copy import deepcopy

import pytest

from domain.rolling.timed_pareto import asof_score, run_timed_pareto


def payload(n=4):
    return {
        "stays": [
            {"stay_id": sid, "first_careunit": "MICU", "outtime": "ignored"}
            for sid in range(1, n + 1)
        ],
        "scores": [
            {
                "stay_id": sid,
                "hour_index": hour,
                "sofa_total": total,
                "components": {"renal": total},
                "missing_components": [],
            }
            for sid in range(1, n + 1)
            for hour, total in [(24, 2), (26, 4), (48, 20)]
        ],
    }


class Solver:
    def __init__(self, *, displace=False):
        self.calls = []
        self.displace = displace

    def __call__(self, **kwargs):
        self.calls.append(deepcopy(kwargs))
        rows = kwargs["candidate_rows"]
        n_beds = kwargs["resource_overrides"]["n_beds"]
        rows = rows[:n_beds]
        rotate = int(rows[0]["sofa_total"] >= 4)
        if self.displace and rotate:
            rows = rows[:1]
        amap = {r["stay_id"]: (idx + rotate) % n_beds + 1 for idx, r in enumerate(rows)}
        previous = kwargs["occupied_beds"]
        values = {
            "occupancy": len(amap),
            "high_risk": 0,
            "wait": sum(int(r["priority_weight"] * 1000) for r in rows),
            "overload": sum(int(r["sofa_total"]) for r in rows),
            "zone_mismatch": 0,
            "balance": 0,
            "move": sum(
                sid in previous and previous[sid] != bed for sid, bed in amap.items()
            ),
        }
        bounds = kwargs.get("epsilon_bounds") or {}
        feasible = all(
            values[k] >= bound
            if k in ("occupancy", "high_risk", "wait")
            else values[k] <= bound
            for k, bound in bounds.items()
        )
        return {
            "solver_status": "OPTIMAL" if feasible else "INFEASIBLE",
            "assigned": len(amap),
            "top_assignments": [
                {"stay_id": sid, "bed_id": bed} for sid, bed in amap.items()
            ],
            "multiobjective": {"values": values},
        }


def test_relative_replay_uses_asof_scores_and_counts_forced_bed_change():
    solver = Solver()
    report = run_timed_pareto(
        payload(), solve=solver, n_beds=2, n_steps=2, admission_rate=0, discharge_rate=0
    )
    first, second, third = report["history"]
    assert first["f5_move"] == 0
    assert first["common_patients"] == 0 and first["similarity"] == 1
    assert second["f5_move"] == 2 and second["churn"] == 1
    assert third["f5_move"] == 0
    assert all(h["patient_conservation"] for h in report["history"])
    assert [r["sofa_total"] for r in first["scores"]] == [2] * 4
    assert [r["sofa_total"] for r in second["scores"]] == [4] * 4
    assert all(
        r["score_hour"] <= r["clinical_hour"]
        for h in report["history"]
        for r in h["scores"]
    )
    # reference + seven payoff solves + one collapsed epsilon grid per step.
    for previous_beds in ({}, second["predecision_beds"], third["predecision_beds"]):
        calls = [c for c in solver.calls if c["occupied_beds"] == previous_beds]
        assert calls
        assert all(not c["persist"] and c["solver_seed"] == 0 for c in calls)
    assert second["front"][0]["extras"]["assignments"] == second["assignments"]


def test_future_scores_cannot_change_earlier_decisions():
    before = payload()
    after = deepcopy(before)
    for row in after["scores"]:
        if row["hour_index"] == 48:
            row["sofa_total"] = 0
            row["components"] = {"renal": 0}
    opts = {"n_beds": 2, "n_steps": 2, "admission_rate": 0, "discharge_rate": 0}
    left = run_timed_pareto(before, solve=Solver(), **opts)
    right = run_timed_pareto(after, solve=Solver(), **opts)
    assert left == right


def test_every_solve_at_a_decision_uses_identical_context():
    solver = Solver()
    run_timed_pareto(
        payload(), solve=solver, n_beds=2, n_steps=1, admission_rate=0, discharge_rate=0
    )
    groups = {}
    for call in solver.calls:
        score = call["candidate_rows"][0]["sofa_total"]
        context = {
            k: call[k]
            for k in (
                "candidate_rows",
                "occupied_beds",
                "retain_occupied",
                "constraint_modes",
                "resource_overrides",
            )
        }
        assert context == groups.setdefault(score, context)


def test_displaced_incumbent_returns_to_waiting_in_opt_in_research_mode():
    report = run_timed_pareto(
        payload(),
        solve=Solver(displace=True),
        n_beds=2,
        n_steps=1,
        admission_rate=0,
        discharge_rate=0,
        retain_occupied=False,
    )
    step = report["history"][1]
    assert step["displaced_to_waiting"]
    assert set(step["displaced_to_waiting"]) <= set(step["waiting"])
    assert step["patient_conservation"]


def test_incumbent_removal_is_rejected_by_default():
    with pytest.raises(RuntimeError, match="removed an incumbent"):
        run_timed_pareto(
            payload(),
            solve=Solver(displace=True),
            n_beds=2,
            n_steps=1,
            admission_rate=0,
            discharge_rate=0,
        )


def test_all_missing_warmup_is_excluded_instead_of_zero_priority():
    data = payload(2)
    for score in data["scores"]:
        if score["stay_id"] == 1:
            score["components"] = {"renal": None}
            score["missing_components"] = [
                "renal",
                "liver",
                "coagulation",
                "respiratory",
                "cardiovascular",
                "cns",
            ]
    report = run_timed_pareto(data, solve=Solver(), n_beds=1, n_steps=0)
    assert report["excluded_no_observed_warmup_score"] == [1]
    assert report["sample_stay_ids"] == [2]


def test_24h_events_are_deterministic_and_patients_never_disappear():
    opts = {
        "n_beds": 2,
        "n_steps": 12,
        "initial_candidates": 2,
        "admission_rate": 0.5,
        "discharge_rate": 0.5,
    }
    left = run_timed_pareto(payload(8), solve=Solver(), **opts)
    right = run_timed_pareto(payload(8), solve=Solver(), **opts)
    assert left == right
    assert len(left["history"]) == 13
    assert left["history"][-1]["hour"] == 24
    assert all(h["patient_conservation"] for h in left["history"])
    assert all(
        len(h["assignments"]) == h["objective_values"].get("occupancy", 0)
        for h in left["history"]
    ), "later discharges must not mutate historical snapshots"
    assert left["history"][1]["arrivals"] and left["history"][1]["discharged"]


def test_asof_has_no_implicit_future_fallback():
    assert asof_score([{"hour_index": 24}], 22) is None
    assert asof_score([{"hour_index": 24}], 24) == {"hour_index": 24}


def test_failed_payoff_is_not_interpreted_as_zero_objectives():
    solver = Solver()

    def fail_anchor(**kwargs):
        if kwargs.get("lambda_weights"):
            return {"solver_status": "UNKNOWN"}
        return solver(**kwargs)

    with pytest.raises(RuntimeError, match="Reference/payoff solve failed: UNKNOWN"):
        run_timed_pareto(payload(), solve=fail_anchor, n_beds=2, n_steps=0)


def test_infeasible_grid_is_recorded_as_solver_status():
    from domain.optimizer.cp_sat import AssignmentSolveError

    solver = Solver()

    def infeasible_scan(**kwargs):
        if kwargs.get("objective_mode") == "epsilon_constraint":
            raise AssignmentSolveError("INFEASIBLE")
        return solver(**kwargs)

    report = run_timed_pareto(payload(), solve=infeasible_scan, n_beds=2, n_steps=0)
    assert report["history"][0]["front"] == []
    assert {p["status"] for p in report["history"][0]["epsilon_scan"]["points"]} == {
        "INFEASIBLE"
    }


def test_disabled_demand_constraints_preserve_default_resources():
    solver = Solver()
    report = run_timed_pareto(payload(), solve=solver, n_steps=0)
    resources = report["config"]["resources"]
    assert resources["n_beds"] == 20
    assert resources["n_isolation_beds"] == 4
    assert resources["n_ventilators"] == 8
    assert all(
        call["constraint_modes"] == {"isolation": "none", "ventilator": "none"}
        for call in solver.calls
    )


@pytest.mark.parametrize(
    "opts", [{"n_steps": 13}, {"step_hours": 4}, {"discharge_rate": -0.1}]
)
def test_invalid_protocol_parameters_fail(opts):
    with pytest.raises(ValueError):
        run_timed_pareto(payload(), solve=Solver(), **opts)
