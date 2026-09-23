from __future__ import annotations

import pytest
from ortools.sat.python import cp_model

from domain.optimizer.multiobjective import ObjectiveSpec, solve_multiobjective


def _choice_model():
    model = cp_model.CpModel()
    x = model.NewBoolVar("x")
    y = model.NewBoolVar("y")
    model.Add(x + y <= 1)
    specs = [
        ObjectiveSpec("throughput", x + y, "max", 1),
        ObjectiveSpec("benefit", 10 * x + 6 * y, "max", 10),
        ObjectiveSpec("risk", 5 * x + y, "min", 5),
    ]
    return model, x, y, specs


def test_weighted_sum_uses_shared_objective_specs():
    model, x, y, specs = _choice_model()

    result = solve_multiobjective(
        model,
        specs,
        mode="weighted_sum",
        weights={"throughput": 1, "benefit": 1, "risk": 3},
    )

    assert result.status == cp_model.OPTIMAL
    assert result.solver.Value(x) == 0
    assert result.solver.Value(y) == 1
    assert result.objective_values == {"throughput": 1, "benefit": 6, "risk": 1}


def test_lexicographic_locks_each_higher_priority_optimum():
    model, x, y, specs = _choice_model()

    result = solve_multiobjective(
        model,
        specs,
        mode="lexicographic",
        objective_order=["throughput", "benefit", "risk"],
    )

    assert result.status == cp_model.OPTIMAL
    assert result.exact_hierarchy is True
    assert result.solver.Value(x) == 1
    assert result.solver.Value(y) == 0
    assert [stage["objective"] for stage in result.stages] == [
        "throughput",
        "benefit",
        "risk",
    ]
    assert [stage["value"] for stage in result.stages] == [1, 10, 5]


def test_epsilon_constraint_applies_direction_aware_bound():
    model, x, y, specs = _choice_model()

    result = solve_multiobjective(
        model,
        specs,
        mode="epsilon_constraint",
        epsilon_primary="benefit",
        epsilon_bounds={"throughput": 1, "risk": 1},
    )

    assert result.status == cp_model.OPTIMAL
    assert result.solver.Value(x) == 0
    assert result.solver.Value(y) == 1
    assert result.objective_values["risk"] <= 1
    assert result.objective_values["throughput"] >= 1


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"mode": "unknown"}, "objective_mode"),
        (
            {
                "mode": "lexicographic",
                "objective_order": ["benefit", "benefit"],
            },
            "duplicates",
        ),
        (
            {
                "mode": "epsilon_constraint",
                "epsilon_primary": "benefit",
                "epsilon_bounds": {"benefit": 1},
            },
            "cannot also",
        ),
        (
            {
                "mode": "epsilon_constraint",
                "epsilon_primary": "benefit",
                "epsilon_bounds": {"risk": 1.5},
            },
            "finite integer",
        ),
    ],
)
def test_invalid_multiobjective_configuration_is_rejected(kwargs, message):
    model, _x, _y, specs = _choice_model()

    with pytest.raises(ValueError, match=message):
        solve_multiobjective(model, specs, **kwargs)
