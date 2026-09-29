"""Unit tests for S2-MOO phase-4 scenario pack (no database)."""

from __future__ import annotations

from domain.optimizer.moo_scenarios import (
    SCENARIOS,
    ScenarioSpec,
    list_scenarios,
    run_all_scenarios,
    run_scenario_pack,
    summarize_for_status,
    write_scenario_reports,
)


def test_six_scenarios_defined():
    specs = list_scenarios()
    assert len(specs) == 6
    assert {s.id for s in specs} == {s.id for s in SCENARIOS}
    assert any(s.resource_overrides.get("n_beds") == 12 for s in specs)


def test_run_scenario_pack_with_fake_solve(tmp_path):
    calls: list[str] = []

    def fake_solve(**kwargs):
        mode = kwargs.get("objective_mode", "?")
        calls.append(mode)
        overrides = kwargs.get("resource_overrides") or {}
        n_beds = int(overrides.get("n_beds", 20))
        return {
            "solver_status": "OPTIMAL",
            "assigned": min(n_beds, 10),
            "n_beds": n_beds,
            "n_stays": 50,
            "multiobjective": {
                "values": {
                    "occupancy": min(n_beds, 10),
                    "high_risk": 3,
                    "wait": 1000,
                    "overload": 0,
                    "zone_mismatch": 1,
                    "move": 0,
                    "balance": 0,
                },
                "wall_time_seconds": 0.1,
                "exact_hierarchy": True,
            },
            "evaluation": {
                "assignment_rate": 0.2,
                "high_risk_waiting": 2,
                "zone_match_rate": 0.8,
                "isolation_utilization": 0.5,
                "ventilator_utilization": 0.4,
                "solve_time_seconds": 0.1,
            },
        }

    scenario = ScenarioSpec(
        id="S2_bed_shortage",
        name="总床位不足",
        description="test",
        resource_overrides={"n_beds": 12, "n_isolation_beds": 2, "n_ventilators": 5},
    )
    rows = run_scenario_pack(fake_solve, scenario=scenario, include_epsilon=True)
    assert len(rows) == 3
    assert {r["method"] for r in rows} == {
        "weighted_sum",
        "lexicographic",
        "epsilon_mid",
    }
    assert all(r["status"] == "OPTIMAL" for r in rows)
    assert "weighted_sum" in calls and "lexicographic" in calls


def test_run_all_scenarios_and_write(tmp_path):
    def fake_solve(**kwargs):
        return {
            "solver_status": "OPTIMAL",
            "assigned": 5,
            "n_beds": 20,
            "n_stays": 40,
            "multiobjective": {
                "values": {
                    "occupancy": 5,
                    "high_risk": 2,
                    "wait": 500,
                    "overload": 0,
                    "zone_mismatch": 0,
                    "move": 0,
                    "balance": 1,
                },
                "wall_time_seconds": 0.05,
                "exact_hierarchy": True,
            },
            "evaluation": {"high_risk_waiting": 1},
        }

    tiny = [
        ScenarioSpec(id="S1_normal", name="正常", description="d"),
        ScenarioSpec(
            id="S2_bed_shortage",
            name="床不足",
            description="d",
            resource_overrides={"n_beds": 12},
        ),
    ]
    payload = run_all_scenarios(
        fake_solve, scenarios=tiny, include_epsilon=False, split="calib"
    )
    assert len(payload["rows"]) == 4  # 2 scenarios × 2 methods
    paths = write_scenario_reports(payload, out_dir=tmp_path, stamp="test")
    assert (tmp_path / "scenarios_test.json").exists()
    assert (tmp_path / "scenarios_latest.json").exists()
    assert "summary" in paths
    compact = summarize_for_status(payload)
    assert len(compact) == 2
    assert "lexicographic" in compact[0]
