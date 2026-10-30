"""Synthetic trajectory regression tests: all simulation and DB access is blocked."""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest

from application import export_trajectory as cli
from domain.optimizer.constraint_rules import needs_isolation, needs_ventilator
from domain.rl import trajectory
from domain.rl.env import DEFAULT_REWARD_WEIGHTS

REQUIRED_PACK_KEYS = {
    "protocol_version", "created_at", "source", "n_beds", "step_hours",
    "n_steps", "summary", "transitions", "notes",
}
REQUIRED_TRANSITION_KEYS = {
    "t", "dt_hours", "state", "action", "reward_components",
    "constraint_violation", "prev_occupied", "next_state", "constraint_check_status",
}
REQUIRED_STATE_KEYS = {"occupied", "free_beds", "avg_sofa", "avg_weight"}
REQUIRED_ACTION_KEYS = {"admitted", "discharged", "policy"}
REQUIRED_REWARD_KEYS = {"occupancy", "wait", "wait_proxy"}


@pytest.fixture(autouse=True)
def forbid_database_and_unstubbed_simulation(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("trajectory tests must not run a real simulation or access the DB")

    monkeypatch.setattr("domain.rolling.engine.get_engine", forbidden)
    monkeypatch.setattr(trajectory, "run_rolling_simulation", forbidden)


@pytest.fixture
def synthetic_history():
    return [
        {
            "step": 0, "occupied": 2, "admitted": 2, "discharged": 0,
            "avg_sofa": 5.0, "avg_weight": 1.5,
            "assignments": [{"stay_id": 101, "bed_id": 1}, {"stay_id": 102, "bed_id": 2}],
            "constraint_violation": False, "solver_status": "OPTIMAL",
        },
        {
            "step": 1, "occupied": 3, "admitted": 2, "discharged": 1,
            "avg_sofa": 6.0, "avg_weight": 2.0,
            "assignments": [
                {"stay_id": 102, "bed_id": 2}, {"stay_id": 103, "bed_id": 1},
                {"stay_id": 104, "bed_id": 3},
            ],
            "admitted_stay_ids": [103, 104], "discharged_stay_ids": [101],
            "returned_to_queue_stay_ids": [],
            "constraint_violation": False, "solver_status": "OPTIMAL",
        },
        {
            "step": 2, "occupied": 2, "admitted": 1, "discharged": 1,
            "avg_sofa": 7.0, "avg_weight": 2.25,
            "assignments": [{"stay_id": 103, "bed_id": 1}, {"stay_id": 105, "bed_id": 3}],
            "admitted_stay_ids": [105], "discharged_stay_ids": [102],
            "returned_to_queue_stay_ids": [104],
            "constraint_violation": True, "solver_status": "FEASIBLE",
        },
    ]


@pytest.fixture
def export_case(tmp_path, monkeypatch, synthetic_history):
    simulation = {
        "history": synthetic_history, "total_steps": 2, "n_beds": 4, "step_hours": 2,
        "total_admissions": 5, "total_discharges": 2,
        "final_occupancy": 2, "bed_utilization_pct": 50.0,
    }
    runner = Mock(return_value=simulation)
    config = Mock(return_value={"resources": {"n_beds": 8}, "rolling": {"step_hours": 6}})
    monkeypatch.setattr(trajectory, "OUT_DIR", tmp_path / "trajectories")
    monkeypatch.setattr(trajectory, "run_rolling_simulation", runner)
    monkeypatch.setattr(trajectory, "load_yaml", config)
    return simulation, runner, config


def test_needs_isolation_keywords():
    assert needs_isolation("Medical Intensive Care Unit (MICU)") is True
    assert needs_isolation("Floor") is False


def test_needs_ventilator_deterministic():
    assert needs_ventilator(12345) is needs_ventilator(12345)


def test_reward_weights_include_occupancy():
    assert "occupancy" in DEFAULT_REWARD_WEIGHTS


def test_transition_uses_pre_and_post_states_and_post_state_reward(synthetic_history):
    transitions = trajectory._transition_from_history(synthetic_history, step_hours=2, n_beds=4)
    first, second = transitions
    assert first["t"] == 1
    assert first["dt_hours"] == 2
    assert first["state"]["occupied"] == first["prev_occupied"] == 2
    assert first["state"]["free_beds"] == 2
    assert first["state"]["avg_sofa"] == 5.0
    assert first["state"]["avg_weight"] == 1.5
    assert first["next_state"]["occupied"] == 3
    assert first["next_state"]["free_beds"] == 1
    assert first["next_state"]["avg_sofa"] == 6.0
    assert first["next_state"]["avg_weight"] == 2.0
    assert first["next_state"] == second["state"]
    assert first["reward_components"] == {"occupancy": 0.75, "wait": 1.0, "wait_proxy": 1.0}
    assert second["reward_components"] == {"occupancy": 0.5, "wait": 2.0, "wait_proxy": 2.0}
    assert first["constraint_violation"] is False
    assert second["constraint_violation"] is True
    assert first["constraint_check_status"] == second["constraint_check_status"] == "checked"


def test_audit_ids_assignments_and_solver_status_are_preserved_without_aliasing(synthetic_history):
    original = deepcopy(synthetic_history)
    first, second = trajectory._transition_from_history(synthetic_history, step_hours=2, n_beds=4)
    assert first["state"]["assignments"] == synthetic_history[0]["assignments"]
    assert first["next_state"]["assignments"] == synthetic_history[1]["assignments"]
    for transition, snapshot in zip((first, second), synthetic_history[1:]):
        for key in ("admitted_stay_ids", "discharged_stay_ids", "returned_to_queue_stay_ids", "solver_status"):
            assert transition["action"][key] == snapshot[key]
        assert transition["action"]["admitted"] == snapshot["admitted"]
        assert transition["action"]["discharged"] == snapshot["discharged"]
    first["next_state"]["assignments"][0]["stay_id"] = -1
    first["action"]["admitted_stay_ids"].append(-1)
    assert synthetic_history == original
    assert second["state"]["assignments"] == original[1]["assignments"]


@pytest.mark.parametrize("result", [None, False, True, 0, 1, "False", "unknown", [], {}])
def test_constraint_results_require_an_explicit_boolean(result):
    history = [{"occupied": 1, "constraint_violation": result}] * 2
    transition = trajectory._transition_from_history(history, step_hours=2, n_beds=4)[0]
    expected = result if isinstance(result, bool) else None
    assert transition["constraint_violation"] is expected
    assert transition["state"]["constraint_violation"] is expected
    assert transition["next_state"]["constraint_violation"] is expected
    assert transition["constraint_check_status"] == ("unknown" if expected is None else "checked")


def test_old_history_has_unknown_checks_and_no_invented_assignment_or_event_ids():
    history = [{"occupied": 1}, {"step": 1, "occupied": 2, "admitted": 1}]
    transition = trajectory._transition_from_history(history, step_hours=2, n_beds=4)[0]
    assert transition["constraint_violation"] is None
    assert transition["constraint_check_status"] == "unknown"
    assert transition["state"]["constraint_violation"] is None
    assert "assignments" not in transition["state"]
    assert "assignments" not in transition["next_state"]
    assert transition["action"] == {"admitted": 1, "discharged": 0, "policy": "rolling_cp_sat_fill"}


@pytest.mark.parametrize("history", [[], [{"occupied": 2}]])
def test_no_transition_without_two_snapshots(history):
    assert trajectory._transition_from_history(history, step_hours=2, n_beds=4) == []


def test_protocol_schema_on_exported_synthetic_pack(export_case):
    simulation, runner, config = export_case
    result = trajectory.export_rolling_trajectory(n_steps=2, out_name="synthetic.json")
    runner.assert_called_once_with(n_steps=2, persist=False)
    config.assert_called_once_with("optimizer.yaml")
    path, latest = Path(result["path"]), Path(result["latest"])
    assert path == trajectory.OUT_DIR / "synthetic.json"
    assert latest == trajectory.OUT_DIR / "rolling_traj_latest.json"
    assert path.read_bytes() == latest.read_bytes()
    pack = json.loads(path.read_text(encoding="utf-8"))
    assert REQUIRED_PACK_KEYS <= set(pack)
    assert pack["protocol_version"] == "2.0"
    assert pack["n_beds"] == 4
    assert pack["step_hours"] == 2
    assert pack["n_steps"] == result["n_transitions"] == len(pack["transitions"]) == 2
    assert pack["summary"] == {key: simulation[key] for key in (
        "total_admissions", "total_discharges", "final_occupancy", "bed_utilization_pct",
    )}
    assert "not priority_served or waiting time" in pack["reward_semantics"]["wait"]
    assert "not an ICUEnv/PPO training reward" in pack["reward_semantics"]["wait_proxy"]
    assert any("not evidence of RL training reward alignment" in note for note in pack["notes"])
    assert any("Not a MIMIC bedside event log" in note for note in pack["notes"])
    assert any("null means unknown" in note for note in pack["notes"])
    assert any("1.0 state was after" in note for note in pack["notes"])
    for transition in pack["transitions"]:
        assert REQUIRED_TRANSITION_KEYS <= set(transition)
        assert REQUIRED_STATE_KEYS <= set(transition["state"])
        assert REQUIRED_STATE_KEYS <= set(transition["next_state"])
        assert REQUIRED_ACTION_KEYS <= set(transition["action"])
        assert REQUIRED_REWARD_KEYS <= set(transition["reward_components"])
    assert pack["transitions"][0]["action"]["admitted_stay_ids"] == [103, 104]
    assert pack["transitions"][1]["action"]["returned_to_queue_stay_ids"] == [104]
    assert pack["transitions"][1]["constraint_violation"] is True


def test_missing_engine_checks_serialize_as_null(export_case):
    simulation, _, _ = export_case
    for snapshot in simulation["history"]:
        snapshot.pop("constraint_violation")
    result = trajectory.export_rolling_trajectory(n_steps=2)
    pack = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    for transition in pack["transitions"]:
        assert transition["constraint_violation"] is None
        assert transition["state"]["constraint_violation"] is None
        assert transition["next_state"]["constraint_violation"] is None
        assert transition["constraint_check_status"] == "unknown"


def test_zero_steps_exports_initial_summary_without_transitions(export_case):
    simulation, runner, _ = export_case
    simulation.update(total_steps=0, total_admissions=2, total_discharges=0)
    simulation["history"] = simulation["history"][:1]
    result = trajectory.export_rolling_trajectory(n_steps=0)
    runner.assert_called_once_with(n_steps=0, persist=False)
    assert result["n_transitions"] == 0
    pack = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    assert pack["n_steps"] == 0
    assert pack["summary"]["total_admissions"] == 2
    assert pack["transitions"] == []


def test_missing_simulation_dimensions_use_configuration(export_case):
    simulation, _, _ = export_case
    simulation.pop("n_beds")
    simulation.pop("step_hours")
    result = trajectory.export_rolling_trajectory(n_steps=2)
    pack = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    assert pack["n_beds"] == 8
    assert pack["step_hours"] == 6
    assert pack["transitions"][0]["dt_hours"] == 6
    assert pack["transitions"][0]["next_state"]["free_beds"] == 5


@pytest.mark.parametrize("n_steps", [-1, 10_001, 10**20, 1.5, "2", None, True, False, float("inf"), float("nan")])
def test_invalid_steps_fail_before_simulation_config_or_file_writes(n_steps, export_case):
    _, runner, config = export_case
    with pytest.raises(ValueError, match="n_steps"):
        trajectory.export_rolling_trajectory(n_steps=n_steps)
    runner.assert_not_called()
    config.assert_not_called()
    assert not trajectory.OUT_DIR.exists()


@pytest.mark.parametrize("name", [
    "", ".", "..", ".json", "../escape.json", "..\\escape.json", "sub/trace.json", "sub\\trace.json",
    "/absolute.json", "C:\\outside.json", "C:trace.json", "\\\\server\\share\\trace.json",
    "trace.json:stream", "trace.txt", "trace.json.", "trace.json ", " trace.json",
    "NUL.json", "con.json", "COM1.json", "LPT9.json", "CONIN$.json", "NUL .json", "COM¹.json",
    "bad?.json", "bad*.json", "bad|.json",
    'bad".json', "bad<.json", "bad>.json", "bad\x00.json", "bad\n.json", "x" * 251 + ".json", 123,
])
def test_invalid_name_fails_before_simulation_config_or_file_writes(name, export_case):
    _, runner, config = export_case
    with pytest.raises(ValueError, match="JSON basename"):
        trajectory.export_rolling_trajectory(n_steps=2, out_name=name)
    runner.assert_not_called()
    config.assert_not_called()
    assert not trajectory.OUT_DIR.exists()


@pytest.mark.parametrize("name", ["trace.json", "trace.JSON", "轨迹.json", "trace output.json", ".hidden.json", "rolling_traj_latest.json"])
def test_legal_json_basenames_stay_in_output_directory(name, export_case):
    result = trajectory.export_rolling_trajectory(n_steps=2, out_name=name)
    path = Path(result["path"])
    assert path.name == name
    assert path.parent == trajectory.OUT_DIR
    assert json.loads(path.read_text(encoding="utf-8"))["protocol_version"] == "2.0"


@pytest.mark.parametrize("name", ["trace.json", "rolling_traj_latest.json"])
def test_existing_output_symlink_cannot_redirect_writes(name, export_case, tmp_path):
    _, runner, config = export_case
    outside = tmp_path / "outside.json"
    outside.write_text("untouched", encoding="utf-8")
    trajectory.OUT_DIR.mkdir()
    try:
        (trajectory.OUT_DIR / name).symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("file symlinks are unavailable on this platform")
    with pytest.raises(ValueError, match="inside the trajectory directory"):
        trajectory.export_rolling_trajectory(n_steps=2, out_name="trace.json")
    assert outside.read_text(encoding="utf-8") == "untouched"
    runner.assert_not_called()
    config.assert_not_called()


@pytest.mark.parametrize("args, expected_steps", [([], 12), (["--steps", "2", "--name", "cli.json"], 2)])
def test_cli_exports_json_without_database_access(args, expected_steps, export_case, monkeypatch, capsys):
    _, runner, _ = export_case
    monkeypatch.setattr(sys, "argv", ["export_trajectory", *args])
    cli.main()
    runner.assert_called_once_with(n_steps=expected_steps, persist=False)
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "ok"
    assert Path(output["path"]).is_file()
    assert output["n_transitions"] == 2
    if args:
        assert Path(output["path"]).name == "cli.json"
    else:
        assert Path(output["path"]).name.startswith("rolling_traj_")


@pytest.mark.parametrize("args", [
    ["--steps", "-1"], ["--steps", "10001"], ["--steps", "2.5"], ["--steps", "abc"],
    ["--name", "../escape.json"], ["--name", "trace.txt"], ["--name", ""],
])
def test_cli_invalid_arguments_exit_cleanly_before_any_work(args, export_case, monkeypatch, capsys):
    _, runner, config = export_case
    monkeypatch.setattr(sys, "argv", ["export_trajectory", *args])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "error:" in output.err
    assert "Traceback" not in output.err
    runner.assert_not_called()
    config.assert_not_called()
    assert not trajectory.OUT_DIR.exists()
