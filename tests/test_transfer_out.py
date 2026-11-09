"""Transfer-out as a decision variable (no f6 objective)."""

from __future__ import annotations

import pytest

from domain.optimizer.cp_sat import run_assignment

# 4 beds in two zones; incumbents sit in MICU.
RESOURCES = {
    "n_beds": 4,
    "n_isolation_beds": 0,
    "n_ventilators": 8,
    "bed_zones": [[1, 2, "MICU"], [3, 2, "SICU"]],
}

INCUMBENTS = [
    {"stay_id": 11, "sofa_total": 2, "priority_weight": 1.2, "first_careunit": "MICU"},
    {"stay_id": 22, "sofa_total": 2, "priority_weight": 1.2, "first_careunit": "MICU"},
]
PREVIOUS = {11: 1, 22: 2}


def _solve(rows, **kwargs):
    return run_assignment(
        persist=False,
        candidate_rows=rows,
        previous_beds=PREVIOUS,
        retain_occupied=True,
        resource_overrides=RESOURCES,
        solver_seed=0,
        **kwargs,
    )


def _assigned_ids(result):
    return {int(r["stay_id"]) for r in result["top_assignments"]}


def test_no_transferable_means_no_transfer_variable():
    result = _solve(INCUMBENTS)
    assert result["transferred"] == []
    assert result["n_transferred"] == 0
    assert result["transferable"] == []
    assert result["max_transfers"] is None


def test_retained_incumbent_stays_when_not_transferable():
    result = _solve(INCUMBENTS)
    assert _assigned_ids(result) == {11, 22}


def test_transfer_frees_a_bed_for_a_waiting_patient():
    rows = INCUMBENTS + [
        # Higher priority than 11, so trading 11 out for 33 raises f1.
        {"stay_id": 33, "sofa_total": 6, "priority_weight": 1.6, "first_careunit": "MICU"},
        {"stay_id": 44, "sofa_total": 6, "priority_weight": 1.6, "first_careunit": "MICU"},
        {"stay_id": 55, "sofa_total": 6, "priority_weight": 1.6, "first_careunit": "MICU"},
    ]
    baseline = _solve(rows)
    assert baseline["n_transferred"] == 0
    assert len(_assigned_ids(baseline)) == 4

    with_transfer = _solve(rows, transferable=[11, 22], max_transfers=1)
    assert with_transfer["n_transferred"] <= 1
    assigned = _assigned_ids(with_transfer)
    assert len(assigned) == 4
    # A low-priority incumbent is replaced by a higher-priority wait-list patient.
    assert with_transfer["objective"]["f1_priority_total"] >= baseline["objective"]["f1_priority_total"]
    assert set(with_transfer["transferred"]) <= {11, 22}


def test_max_transfers_cap_is_respected():
    rows = INCUMBENTS + [
        {"stay_id": 33, "sofa_total": 6, "priority_weight": 1.9, "first_careunit": "MICU"},
        {"stay_id": 44, "sofa_total": 6, "priority_weight": 1.9, "first_careunit": "MICU"},
    ]
    for cap in (0, 1, 2):
        result = _solve(rows, transferable=[11, 22], max_transfers=cap)
        assert result["n_transferred"] <= cap
        assert result["max_transfers"] == cap


def test_transfer_does_not_count_as_a_bed_move():
    rows = INCUMBENTS + [
        {"stay_id": 33, "sofa_total": 6, "priority_weight": 1.9, "first_careunit": "MICU"},
    ]
    result = _solve(rows, transferable=[11, 22], max_transfers=2)
    # Whoever leaves contributes 0 to f5; the remaining incumbent stays put.
    assert result["objective"]["f5_move"] == 0


def test_occupancy_excludes_transferred_patients():
    rows = INCUMBENTS + [
        {"stay_id": 33, "sofa_total": 6, "priority_weight": 1.9, "first_careunit": "MICU"},
    ]
    result = _solve(rows, transferable=[11, 22], max_transfers=1)
    assert result["objective"]["f0_occupancy"] == len(_assigned_ids(result))
    assert set(result["transferred"]).isdisjoint(_assigned_ids(result))


def test_non_incumbent_cannot_be_transferred():
    rows = INCUMBENTS + [
        {"stay_id": 33, "sofa_total": 6, "priority_weight": 1.9, "first_careunit": "MICU"},
    ]
    # 33 has no previous bed, so declaring it transferable is a modelling error.
    with pytest.raises(ValueError, match="previous_beds"):
        _solve(rows, transferable=[33])


@pytest.mark.parametrize("bad", [-1, -5])
def test_negative_max_transfers_rejected(bad):
    with pytest.raises(ValueError, match="max_transfers"):
        _solve(INCUMBENTS, transferable=[11], max_transfers=bad)


def test_transfer_allowed_without_retain_occupied():
    rows = INCUMBENTS + [
        {"stay_id": 33, "sofa_total": 6, "priority_weight": 1.9, "first_careunit": "MICU"},
    ]
    result = run_assignment(
        persist=False,
        candidate_rows=rows,
        previous_beds=PREVIOUS,
        retain_occupied=False,
        resource_overrides=RESOURCES,
        solver_seed=0,
        transferable=[11, 22],
        max_transfers=1,
    )
    # Incumbents may also fall back to waiting, so no incarnation is forced.
    assert result["n_transferred"] <= 1


# ── end-to-end replay: SOFA gate + transfer decision ─────────────────────
def _replay_payload():
    """Everyone is unstable at hour 24 and recovers by hour 26.

    That makes the scenario independent of the random candidate sampling:
    incumbents reach clinical hour 26 at step 1 (SOFA 2, eligible), while the
    step-1 arrivals read clinical hour 24 (SOFA 6, higher priority), so exactly
    one step-down is profitable.
    """
    stays, scores = [], []
    for sid in range(1, 7):
        stays.append({"stay_id": sid, "first_careunit": "MICU"})
        for hour in range(24, 49, 2):
            sofa = 6 if hour == 24 else 2
            scores.append(
                {
                    "stay_id": sid,
                    "hour_index": hour,
                    "sofa_total": float(sofa),
                    "components": {"renal": sofa},
                    "missing_components": [],
                }
            )
    return {"stays": stays, "scores": scores}


def test_replay_transfers_to_admit_higher_priority_waiters():
    from domain.rolling.timed_pareto import run_timed_pareto

    report = run_timed_pareto(
        _replay_payload(),
        n_beds=4,
        n_steps=2,
        initial_candidates=4,
        admission_rate=1.0,
        discharge_rate=0.0,
        sofa_transfer_max=4.0,
        min_icu_hours=24,
        max_transfers=1,
    )
    first, second, third = report["history"]
    assert first["transferred"] == []
    assert first["n_eligible_transfer"] == 0  # no incumbents yet
    assert second["n_eligible_transfer"] == 4  # all four incumbents qualify
    assert len(second["transferred"]) == 1
    assert second["f5_move"] == 0  # leaving is not a bed move
    assert all(h["patient_conservation"] for h in report["history"])
    # Five-way partition: pending + waiting + occupied + transferred + discharged.
    for h in report["history"]:
        occupied = set(h["assignments"])
        waiting = set(h["waiting"])
        pending = set(h["pending"])
        transferred = set(h["transferred_total"])
        discharged = set(h["discharged_total"])
        parts = [occupied, waiting, pending, transferred, discharged]
        assert sum(len(p) for p in parts) == 6
        assert len(set().union(*parts)) == 6
    # Transfers accumulate and never exceed the per-step cap.
    assert set(second["transferred_total"]) <= set(third["transferred_total"])
    assert len(third["transferred_total"]) <= 2 * 1


def test_replay_without_threshold_never_transfers():
    from domain.rolling.timed_pareto import run_timed_pareto

    report = run_timed_pareto(
        _replay_payload(),
        n_beds=4,
        n_steps=2,
        initial_candidates=4,
        admission_rate=1.0,
        discharge_rate=0.0,
    )
    assert all(h["transferred"] == [] for h in report["history"])
    assert all(h["n_eligible_transfer"] == 0 for h in report["history"])


def test_min_icu_hours_gate_blocks_transfer():
    from domain.rolling.timed_pareto import run_timed_pareto

    report = run_timed_pareto(
        _replay_payload(),
        n_beds=4,
        n_steps=2,
        initial_candidates=4,
        admission_rate=1.0,
        discharge_rate=0.0,
        sofa_transfer_max=4.0,
        min_icu_hours=200,  # unreachable within a 28h clinical window
    )
    assert all(h["n_eligible_transfer"] == 0 for h in report["history"])
    assert all(h["transferred"] == [] for h in report["history"])


def test_sofa_gate_blocks_transfer_of_unstable_patients():
    from domain.rolling.timed_pareto import run_timed_pareto

    report = run_timed_pareto(
        _replay_payload(),
        n_beds=4,
        n_steps=2,
        initial_candidates=4,
        admission_rate=1.0,
        discharge_rate=0.0,
        sofa_transfer_max=1.0,  # below every patient's SOFA of 2
        min_icu_hours=24,
        max_transfers=1,
    )
    assert all(h["n_eligible_transfer"] == 0 for h in report["history"])
    assert all(h["transferred"] == [] for h in report["history"])


@pytest.mark.parametrize("opts", [{"max_transfers": -1}, {"min_icu_hours": -1}])
def test_invalid_transfer_parameters_rejected(opts):
    from domain.rolling.timed_pareto import run_timed_pareto

    with pytest.raises(ValueError):
        run_timed_pareto(
            _replay_payload(),
            n_beds=4,
            n_steps=1,
            sofa_transfer_max=4.0,
            **opts,
        )
