from __future__ import annotations

from domain.optimizer.objectives import OBJECTIVES


def test_registry_has_all_six_objectives():
    assert set(OBJECTIVES) == {
        "occupancy",
        "wait",
        "overload",
        "balance",
        "zone_mismatch",
        "move",
    }


def test_objective_senses():
    assert OBJECTIVES["occupancy"].sense == "max"
    assert OBJECTIVES["wait"].sense == "max"
    for name in ("overload", "balance", "zone_mismatch", "move"):
        assert OBJECTIVES[name].sense == "min"


def test_every_objective_has_a_positive_bound():
    class _Ctx:
        n_beds = 20
        weights = [1000, 2200]
        sofa_vals = [0, 12]

    for spec in OBJECTIVES.values():
        assert spec.bound(_Ctx()) >= 1
