"""H=1 rolling loop: re-solve, commit one step, persist."""

from __future__ import annotations

from copy import deepcopy

from domain.rolling.engine import run_rolling_simulation


def patient(sid: int, priority: float, sofa: float) -> dict:
    return {
        "stay_id": sid,
        "priority_weight": priority,
        "sofa_total": sofa,
        "first_careunit": "MICU",
    }


class FakeSolver:
    """Keep incumbents in place and fill free beds in candidate order."""

    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(deepcopy(kwargs))
        rows = kwargs["candidate_rows"]
        n_beds = int(kwargs["resource_overrides"]["n_beds"])
        previous = kwargs["previous_beds"]
        bed_map: dict[int, int] = {}
        used: set[int] = set()
        for sid, bed in previous.items():
            if sid in {int(r["stay_id"]) for r in rows} and 1 <= bed <= n_beds:
                bed_map[int(sid)] = int(bed)
                used.add(int(bed))
        for row in rows:
            sid = int(row["stay_id"])
            if sid in bed_map:
                continue
            for bed in range(1, n_beds + 1):
                if bed not in used:
                    bed_map[sid] = bed
                    used.add(bed)
                    break
        assignments = [
            {"stay_id": sid, "bed_id": bed}
            for sid, bed in sorted(bed_map.items())
        ]
        assigned_priority = sum(
            int(row["priority_weight"] * 1000)
            for row in rows
            if int(row["stay_id"]) in bed_map
        )
        assigned_sofa = sum(
            int(row["sofa_total"])
            for row in rows
            if int(row["stay_id"]) in bed_map
        )
        moved = sum(
            1
            for sid, bed in bed_map.items()
            if sid in previous and previous[sid] != bed
        )
        values = {
            "occupancy": len(bed_map),
            "wait": assigned_priority,
            "overload": assigned_sofa,
            "balance": 0,
            "zone_mismatch": 0,
            "move": moved,
            "zone_loads": [len(bed_map)],
        }
        return {
            "run_id": "fake",
            "solver_status": "OPTIMAL",
            "assigned": len(bed_map),
            "n_stays": len(rows),
            "n_beds": n_beds,
            "objective": values,
            "evaluation": {"assignment_rate": len(bed_map) / len(rows)},
            "resources": {"isolation_beds_used": "0/0", "ventilators_used": "0/0"},
            "top_assignments": assignments,
            "transferred": [],
            "ward_patients": [],
        }


class MemoryStore:
    def __init__(self):
        self.started = []
        self.steps = []
        self.finished = []

    def start_run(self, run_id, config):
        self.started.append((run_id, config))

    def save_step(self, run_id, record):
        self.steps.append((run_id, record))

    def finish_run(self, run_id, summary):
        self.finished.append((run_id, summary))


def test_rolling_loop_reoptimizes_every_step_and_keeps_waiting():
    solver = FakeSolver()
    result = run_rolling_simulation(
        n_steps=2,
        patients=[patient(i, 1.0 + i, i) for i in range(1, 6)],
        solve=solver,
        resource_overrides={"n_beds": 2},
        initial_candidates=4,
        admission_rate=0,
        discharge_rate=0,
        seed=0,
    )
    assert result["status"] == "ok"
    assert len(result["history"]) == 3
    assert len(solver.calls) == 3
    assert len(result["history"][0]["assignments"]) == 2
    assert len(result["history"][0]["waiting"]) == 2
    assert all(row["patient_conservation"] for row in result["history"])
    assert result["total_admissions"] == 2
    assert result["final_occupancy"] == 2


def test_previous_beds_are_passed_to_every_later_solve():
    solver = FakeSolver()
    result = run_rolling_simulation(
        n_steps=2,
        patients=[patient(i, 1.0 + i, i) for i in range(1, 5)],
        solve=solver,
        resource_overrides={"n_beds": 2},
        initial_candidates=4,
        admission_rate=0,
        discharge_rate=0,
        seed=0,
    )
    first = result["history"][0]["assignments"]
    later = result["history"][1]["assignments"]
    assert solver.calls[0]["previous_beds"] == {}
    assert solver.calls[1]["previous_beds"] == first
    assert solver.calls[2]["previous_beds"] == later
    assert all(call["retain_occupied"] for call in solver.calls)


def test_memory_store_receives_start_steps_and_finish():
    store = MemoryStore()
    result = run_rolling_simulation(
        n_steps=2,
        patients=[patient(i, 1.0 + i, i) for i in range(1, 5)],
        solve=FakeSolver(),
        store=store,
        resource_overrides={"n_beds": 2},
        initial_candidates=4,
        admission_rate=0,
        discharge_rate=0,
        seed=0,
    )
    assert store.started and store.started[0][0] == result["run_id"]
    assert len(store.steps) == len(result["history"]) == 3
    assert store.finished and store.finished[0][0] == result["run_id"]
    assert store.steps[0][1]["step"] == 0


def test_discharge_events_do_not_mutate_historical_snapshots():
    result = run_rolling_simulation(
        n_steps=1,
        patients=[patient(i, 1.0 + i, i) for i in range(1, 5)],
        solve=FakeSolver(),
        resource_overrides={"n_beds": 2},
        initial_candidates=4,
        admission_rate=0,
        discharge_rate=1.0,
        seed=0,
    )
    assert result["total_discharges"] == 2
    assert result["history"][0]["occupied"] == 2
    assert result["history"][0]["discharged"] == []
    assert result["history"][1]["discharged"]
    assert all(row["patient_conservation"] for row in result["history"])


def test_plan_uses_the_last_rolling_decision(monkeypatch):
    import application.plan as plan_module

    decision = {
        "run_id": "roll_demo#s1",
        "solver_status": "OPTIMAL",
        "assigned": 1,
        "n_stays": 2,
        "n_beds": 1,
        "objective": {"f0_occupancy": 1, "f1_priority_total": 2000, "zone_loads": [1]},
        "evaluation": {"assignment_rate": 0.5, "zone_match_rate": 1.0},
        "resources": {"isolation_beds_used": "0/0", "ventilators_used": "0/0"},
        "top_assignments": [
            {
                "stay_id": 1,
                "bed_id": 1,
                "bed_type": "MICU",
                "patient_zone": "MICU",
                "zone_match": True,
                "priority_weight": 2.0,
                "sofa_total": 5.0,
            }
        ],
    }
    fake = {
        "run_id": "roll_demo",
        "status": "simulate_ok",
        "final_occupancy": 1,
        "bed_utilization_pct": 100.0,
        "history": [{"step": 1, "hour": 2, "decision": decision}],
    }
    monkeypatch.setattr(plan_module, "run_simulate", lambda n_steps: fake)
    out = plan_module.run_simulation_with_plan(1)
    assert out["plan"]["run_id"] == "roll_demo"
    assert out["plan"]["step"] == 1
    assert out["plan"]["assignments"] == decision["top_assignments"]
    assert out["assign"]["solver_status"] == "OPTIMAL"


def test_real_cp_sat_runs_the_same_loop():
    result = run_rolling_simulation(
        n_steps=1,
        patients=[patient(i, 1.0 + i, i) for i in range(1, 5)],
        resource_overrides={
            "n_beds": 2,
            "n_isolation_beds": 0,
            "n_ventilators": 0,
            "bed_zones": [[1, 2, "MICU"]],
        },
        initial_candidates=4,
        admission_rate=0,
        discharge_rate=0,
        seed=0,
        max_time_seconds=3,
    )
    assert len(result["history"]) == 2
    assert all(row["patient_conservation"] for row in result["history"])
    assert result["history"][0]["status"] in {"OPTIMAL", "FEASIBLE"}
