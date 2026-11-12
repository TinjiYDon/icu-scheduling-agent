"""Case-study checks use invented model inputs, never redistributed MIMIC data."""
from __future__ import annotations

import json
from scripts.case_study import build_case as case


def invented_inputs():
    scores = [8, 8, 6, 6, 5, 5, 2, 5, 4, 1, 2, 0]
    zones = ["MICU"] * 4 + ["SICU"] * 3 + ["CCU"] * 3 + ["NICU", "CCU"]
    patients = {
        f"P{i:02}": {"pid": f"P{i:02}", "preferred_zone": zone}
        for i, zone in enumerate(zones, 1)
    }
    evidence = [
        {"pid": pid, "hour": hour, "sofa12": scores[i]}
        for i, pid in enumerate(patients)
        for hour in range(24, 38, 2)
    ]
    return patients, {(r["pid"], r["hour"]): r for r in evidence}, evidence


def test_static_front_matches_independent_patient_subset_enumeration():
    patients, evidence, _ = invented_inputs()
    rows = case.snapshot(patients, evidence, patients, 0)
    front, _ = case.scan(rows)
    independent = case.independent_static_front(rows)
    assert [case.triple(r) for r in front] == independent["front"]


def test_full_ward_pool_prevents_new_ward_admissions():
    patients, evidence, _ = invented_inputs()
    rows = case.snapshot(patients, evidence, patients, 0)
    result = case.solve(rows, ward_existing=("old-ward-1", "old-ward-2"))
    assert result["ward"] == []
    assert result["f"][0] == 6


def test_saved_snapshots_survive_future_discharge(monkeypatch, tmp_path):
    monkeypatch.setattr(case, "load_inputs", invented_inputs)
    source = tmp_path / "invented.json"
    source.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(case, "SAMPLE", source)
    monkeypatch.setattr(case, "HISTORY", source)
    monkeypatch.setattr(case, "THEORY", None)
    result = case.run_case()
    # Round-trip through the same serialization used for saved audit records.
    saved = json.loads(json.dumps(result))
    for step in saved["rolling"]["history"]:
        assert step["occupied"] == step["executed"]["assignment"]
        assert len(step["occupied"]) == step["executed"]["f"][0] == 6
        parts = [set(step[key]) for key in (
            "occupied", "waiting", "pending", "discharged_total", "ward_total"
        )]
        assert set.union(*parts) == set(saved["patients"])
        assert sum(map(len, parts)) == 12
    assert "P01" in saved["rolling"]["history"][1]["occupied"]
    assert "P01" not in saved["rolling"]["history"][2]["occupied"]
