"""Temporal causality, stable solve context, and patient conservation (no DB)."""

from copy import deepcopy

import pytest

from domain.optimizer.pareto import OBJECTIVE_KEYS
from domain.rolling.timed_pareto import (
    _epsilon_grid,
    _front,
    asof_score,
    quality_objective_names,
    run_timed_pareto,
)


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
        previous = kwargs["previous_beds"]
        values = {
            "occupancy": len(amap),
            "wait": sum(int(r["priority_weight"] * 1000) for r in rows),
            "overload": sum(int(r["sofa_total"]) for r in rows),
            "zone_mismatch": 0,
            "balance": 0,
            "move": sum(
                sid in previous and previous[sid] != bed for sid, bed in amap.items()
            ),
        }
        bounds = kwargs.get("epsilon") or {}
        feasible = all(
            values[k] >= bound if k in ("occupancy", "wait") else values[k] <= bound
            for k, bound in bounds.items()
        )
        return {
            "solver_status": "OPTIMAL" if feasible else "INFEASIBLE",
            "assigned": len(amap),
            "top_assignments": [
                {"stay_id": sid, "bed_id": bed} for sid, bed in amap.items()
            ],
            "objective": {key: values[name] for name, key in OBJECTIVE_KEYS.items()},
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
    for previous_beds in ({}, second["predecision_beds"], third["predecision_beds"]):
        calls = [c for c in solver.calls if c["previous_beds"] == previous_beds]
        assert calls
        assert all(not c["persist"] and c["solver_seed"] == 0 for c in calls)
    assert second["reference_on_sampled_front"] is True
    assert any(
        point["source"] == "reference"
        and point["extras"]["assignments"] == second["assignments"]
        for point in second["front"]
    )


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
                "previous_beds",
                "retain_occupied",
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
    with pytest.raises(RuntimeError, match="without transferring it out"):
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
        if kwargs.get("pivot") and not kwargs.get("epsilon"):
            return {"solver_status": "UNKNOWN"}
        return solver(**kwargs)

    with pytest.raises(RuntimeError, match="Reference/payoff solve failed: UNKNOWN"):
        run_timed_pareto(payload(), solve=fail_anchor, n_beds=2, n_steps=0)


def test_infeasible_grid_is_recorded_as_solver_status():
    from domain.optimizer.cp_sat import AssignmentSolveError

    solver = Solver()

    def infeasible_scan(**kwargs):
        if kwargs.get("pivot") == "wait" and "move" in (kwargs.get("epsilon") or {}):
            raise AssignmentSolveError("INFEASIBLE")
        return solver(**kwargs)

    report = run_timed_pareto(payload(), solve=infeasible_scan, n_beds=2, n_steps=0)
    scan = report["history"][0]["epsilon_scan"]
    assert {p["status"] for p in scan["points"]} == {"INFEASIBLE"}
    # Reference and anchors remain feasible candidates; only grid points failed.
    assert scan["n_feasible"] == 0
    assert scan["n_feasible_candidates"] > 0
    assert any(p["source"] == "reference" for p in report["history"][0]["front"])


def test_disabled_demand_constraints_preserve_default_resources():
    solver = Solver()
    report = run_timed_pareto(payload(), solve=solver, n_steps=0)
    resources = report["config"]["resources"]
    assert resources["n_beds"] == 20
    assert resources["n_isolation_beds"] == 4
    assert resources["n_ventilators"] == 8
    assert report["config"]["constraint_modes"] == {
        "isolation": "none",
        "ventilator": "none",
    }
    assert all(call["resource_overrides"] == resources for call in solver.calls)
    assert list(report["objective_names"]) == list(OBJECTIVE_KEYS)


@pytest.mark.parametrize(
    "opts",
    [
        {"n_steps": 13},
        {"step_hours": 4},
        {"discharge_rate": -0.1},
        {"move_levels": 1},
    ],
)
def test_invalid_protocol_parameters_fail(opts):
    with pytest.raises(ValueError):
        run_timed_pareto(payload(), solve=Solver(), **opts)


def test_move_levels_sweeps_only_f5_and_pins_the_other_axes():
    report = run_timed_pareto(
        payload(),
        solve=Solver(),
        n_beds=2,
        n_steps=2,
        admission_rate=0,
        discharge_rate=0,
        move_levels=4,
    )
    assert report["config"]["move_levels"] == 4
    for snapshot in report["history"]:
        scan = snapshot.get("epsilon_scan")
        if not scan:
            continue
        assert scan["move_levels"] == 4
        grid = scan["grid"]
        # Only ``move`` is swept; the other axes are omitted rather than pinned at
        # their ideal value (pinning would turn soft objectives into hard ones).
        for row in grid:
            assert set(row) == {"occupancy", "move"}
        assert len({row["occupancy"] for row in grid}) == 1
        # No cartesian product is produced: one row per distinct move cap.
        assert len(grid) == len({g["move"] for g in grid})


def test_epsilon_grid_move_mode_spans_the_practical_range():
    payoff = {
        "practical_ideal": {"overload": 10, "zone_mismatch": 0, "move": 0},
        "practical_nadir": {"overload": 40, "zone_mismatch": 12, "move": 8},
        "guard": {"occupancy_min": 18},
    }
    grid = _epsilon_grid(payoff, levels=2, move_levels=5)
    assert [g["move"] for g in grid] == [0, 2, 4, 6, 8]
    assert all(g["occupancy"] == 18 for g in grid)
    # ``overload`` / ``zone_mismatch`` are intentionally absent: constraining a
    # soft objective at its ideal value would distort the sweep.
    assert all("overload" not in g and "zone_mismatch" not in g for g in grid)


def test_epsilon_grid_default_mode_is_the_full_cartesian_product():
    payoff = {
        "practical_ideal": {"overload": 10, "zone_mismatch": 0, "move": 0},
        "practical_nadir": {"overload": 40, "zone_mismatch": 12, "move": 8},
        "guard": {"occupancy_min": 18},
    }
    grid = _epsilon_grid(payoff, levels=2)
    # 2 x 2 x 2 combinations, all axes swept.
    assert len(grid) == 8
    assert {g["move"] for g in grid} == {0, 8}
    assert {g["overload"] for g in grid} == {10, 40}
    assert {g["zone_mismatch"] for g in grid} == {0, 12}


def test_epsilon_grid_asymmetric_level_map_builds_the_p4_grid():
    payoff = {
        "practical_ideal": {"overload": 10, "zone_mismatch": 0, "move": 0},
        "practical_nadir": {"overload": 145, "zone_mismatch": 12, "move": 19},
        "guard": {"occupancy_min": 18},
    }
    grid = _epsilon_grid(
        payoff, levels=2, level_map={"overload": 10, "zone_mismatch": 8}
    )
    # The P4 stage-A grid is exactly 10 x 8 = 80 points per decision step.
    assert len(grid) == 80
    assert {g["overload"] for g in grid} == {
        10, 25, 40, 55, 70, 85, 100, 115, 130, 145
    }
    assert len({g["zone_mismatch"] for g in grid}) == 8
    # An omitted axis must not appear: pinning a minimised objective at its
    # ideal would silently turn it into a hard constraint.
    assert all("move" not in g for g in grid)
    assert all(g["occupancy"] == 18 for g in grid)


def test_epsilon_grid_level_map_drops_axes_marked_one():
    payoff = {
        "practical_ideal": {"overload": 10, "zone_mismatch": 0, "move": 0},
        "practical_nadir": {"overload": 40, "zone_mismatch": 12, "move": 8},
        "guard": {"occupancy_min": 18},
    }
    grid = _epsilon_grid(
        payoff, levels=2, level_map={"overload": 3, "zone_mismatch": 1}
    )
    assert len(grid) == 3
    assert all(set(g) == {"occupancy", "overload"} for g in grid)


def test_epsilon_grid_rejects_unknown_axis():
    payoff = {
        "practical_ideal": {"overload": 10, "zone_mismatch": 0, "move": 0},
        "practical_nadir": {"overload": 40, "zone_mismatch": 12, "move": 8},
        "guard": {"occupancy_min": 18},
    }
    with pytest.raises(ValueError, match="unknown grid objective"):
        _epsilon_grid(payoff, levels=2, level_map={"occupancy": 4})


def test_scan_records_hypervolume_and_knee():
    report = run_timed_pareto(
        payload(),
        solve=Solver(),
        n_beds=2,
        n_steps=2,
        admission_rate=0,
        discharge_rate=0,
        levels=2,
    )
    scans = [h["epsilon_scan"] for h in report["history"] if h.get("epsilon_scan")]
    assert scans
    for scan in scans:
        assert "hypervolume" in scan and scan["hypervolume"] >= 0.0
        assert "nondominated_ratio" in scan
        assert 0.0 <= scan["nondominated_ratio"] <= 1.0
        assert "knee_index" in scan
        if scan["knee_index"] is not None:
            assert scan["knee_source"] is not None


def test_replay_accepts_asymmetric_axis_levels():
    report = run_timed_pareto(
        payload(),
        solve=Solver(),
        n_beds=2,
        n_steps=1,
        admission_rate=0,
        discharge_rate=0,
        level_map={"overload": 3, "zone_mismatch": 2},
    )
    assert report["config"]["level_map"] == {"overload": 3, "zone_mismatch": 2}
    scan = report["history"][0]["epsilon_scan"]
    assert scan["level_map"] == {"overload": 3, "zone_mismatch": 2}
    assert all("move" not in g for g in scan["grid"])


def test_replay_rejects_level_map_without_active_axis():
    with pytest.raises(ValueError):
        run_timed_pareto(
            payload(),
            solve=Solver(),
            n_beds=2,
            n_steps=1,
            level_map={"overload": 1},
        )


def test_move_axis_levels_adds_move_to_the_explicit_grid():
    report = run_timed_pareto(
        payload(),
        solve=Solver(),
        n_beds=2,
        n_steps=1,
        admission_rate=0,
        discharge_rate=0,
        level_map={"overload": 3, "zone_mismatch": 2},
        move_axis_levels=2,
    )
    scan = report["history"][0]["epsilon_scan"]
    assert scan["move_axis_levels"] == 2
    assert scan["level_map"] == {
        "overload": 3,
        "zone_mismatch": 2,
        "move": 2,
    }
    assert scan["grid"]
    assert all("move" in row for row in scan["grid"])
    # The practical range can collapse to one integer level for this toy state;
    # the point of the test is that move is an explicit bound, not a churned
    # column.  A larger level count is covered by the epsilon-grid unit tests.
    assert {row["move"] for row in scan["grid"]} <= {0, 1, 2}
    assert scan["quality_objectives"] == [
        "wait",
        "overload",
        "zone_mismatch",
        "move",
    ]


def test_move_axis_levels_requires_a_level_map():
    with pytest.raises(ValueError, match="requires level_map"):
        run_timed_pareto(
            payload(),
            solve=Solver(),
            n_beds=2,
            n_steps=0,
            move_axis_levels=2,
        )


def test_move_axis_levels_is_mutually_exclusive_with_move_levels():
    with pytest.raises(ValueError, match="mutually exclusive"):
        run_timed_pareto(
            payload(),
            solve=Solver(),
            n_beds=2,
            n_steps=0,
            level_map={"overload": 2},
            move_axis_levels=2,
            move_levels=2,
        )


def test_reference_and_payoff_anchors_are_front_candidates():
    """The reference and the 6+5 anchors must reach the dominance filter.

    ``n_candidates`` counts the reference, the six pure anchors, the five
    practical anchors and every grid point.  Excluding these extras is how a
    reported "front" can contain points the executed reference already beats.
    """
    report = run_timed_pareto(
        payload(),
        solve=Solver(),
        n_beds=2,
        n_steps=1,
        admission_rate=0,
        discharge_rate=0,
        level_map={"overload": 2, "zone_mismatch": 2},
    )
    scan = report["history"][0]["epsilon_scan"]
    assert scan["n_candidates"] == scan["n_grid"] + 1 + 6 + 5
    assert scan["n_feasible_candidates"] >= scan["n_feasible"]
    assert any(
        point["source"] == "reference" for point in report["history"][0]["front"]
    )


def test_max_moves_reaches_every_sub_solve():
    """A move budget must constrain the anchors and the scan, not just one call.

    The payoff anchors set the grid bounds, so if the budget only reached the
    reference solve the swept points would silently ignore it.
    """
    solver = Solver()
    report = run_timed_pareto(
        payload(),
        solve=solver,
        n_beds=2,
        n_steps=1,
        admission_rate=0,
        discharge_rate=0,
        levels=2,
        max_moves=3,
    )
    assert report["config"]["max_moves"] == 3
    assert solver.calls
    assert all(call["max_moves"] == 3 for call in solver.calls)


def test_max_moves_defaults_to_unbounded():
    solver = Solver()
    report = run_timed_pareto(
        payload(),
        solve=solver,
        n_beds=2,
        n_steps=0,
        admission_rate=0,
        discharge_rate=0,
        levels=2,
    )
    assert report["config"]["max_moves"] is None
    assert all(call["max_moves"] is None for call in solver.calls)


def test_replay_rejects_negative_max_moves():
    with pytest.raises(ValueError, match="max_moves"):
        run_timed_pareto(
            payload(),
            solve=Solver(),
            n_beds=2,
            n_steps=0,
            max_moves=-1,
        )


def test_move_is_not_promoted_to_quality_when_only_churned():
    """A free move column must not silently become a hypervolume dimension.

    The old rule added move whenever the front happened to vary on it.  Because
    an unconstrained pivot solve can shuffle beds arbitrarily, that rewarded
    tie-breaking and made 3-D and 4-D hypervolumes get averaged together.
    """
    grid = [{"occupancy": 18, "overload": 130, "zone_mismatch": 2}]
    assert quality_objective_names(grid) == [
        "wait",
        "overload",
        "zone_mismatch",
    ]


def test_quality_objectives_include_move_only_when_it_is_an_explicit_axis():
    grid = [{"occupancy": 18, "overload": 130, "zone_mismatch": 2, "move": 2}]
    assert quality_objective_names(grid) == [
        "wait",
        "overload",
        "zone_mismatch",
        "move",
    ]


def test_front_drops_a_grid_point_dominated_by_the_reference():
    reference = {
        "source": "reference",
        "status": "OPTIMAL",
        "values": {
            "occupancy": 20,
            "wait": 30000,
            "overload": 100,
            "balance": 0,
            "zone_mismatch": 4,
            "move": 0,
        },
        "extras": {},
    }
    grid = {
        "source": "epsilon:1",
        "status": "OPTIMAL",
        "values": {
            "occupancy": 20,
            "wait": 30000,
            "overload": 100,
            "balance": 0,
            "zone_mismatch": 4,
            "move": 5,
        },
        "extras": {},
    }
    assert _front([reference, grid]) == [reference]
