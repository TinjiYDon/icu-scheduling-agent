from __future__ import annotations

import math

import pytest

from domain.optimizer.cp_sat import _objective_coefficient, _resolve_lambda_weights


def test_lambda_defaults_include_all_objectives():
    weights = _resolve_lambda_weights({})

    assert weights == {
        "wait": 10.0,
        "overload": 1.0,
        "balance": 0.1,
        "zone_mismatch": 0.5,
    }


def test_lambda_override_does_not_mutate_other_weights():
    weights = _resolve_lambda_weights(
        {"wait": 3.0, "balance": 0.25},
        {"wait": 2.0, "zone_mismatch": 1.5},
    )

    assert weights == {
        "wait": 2.0,
        "overload": 1.0,
        "balance": 0.25,
        "zone_mismatch": 1.5,
    }


@pytest.mark.parametrize("bad_value", [-1, math.inf, -math.inf, math.nan])
def test_lambda_rejects_invalid_values(bad_value):
    with pytest.raises(ValueError):
        _resolve_lambda_weights({}, {"wait": bad_value})


def test_lambda_rejects_unknown_names():
    with pytest.raises(ValueError, match="unknown lambda"):
        _resolve_lambda_weights({}, {"unknown": 1.0})


def test_lambda_rejects_all_zero():
    with pytest.raises(ValueError, match="greater than zero"):
        _resolve_lambda_weights(
            {},
            {
                "wait": 0,
                "overload": 0,
                "balance": 0,
                "zone_mismatch": 0,
            },
        )


def test_small_positive_lambda_keeps_nonzero_coefficient():
    assert _objective_coefficient(0) == 0
    assert _objective_coefficient(0.001) == 1
