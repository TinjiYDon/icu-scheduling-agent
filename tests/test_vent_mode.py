from __future__ import annotations

import pytest

from domain.optimizer.cp_sat import _resolve_vent_mode, _vent_flags


def test_default_vent_mode_is_none():
    assert _resolve_vent_mode({}) == "none"


@pytest.mark.parametrize("mode", ["none", "pseudo_random", "proxy_rule", "real"])
def test_vent_modes_are_accepted(mode):
    assert _resolve_vent_mode({"vent": {"mode": mode}}) == mode


def test_invalid_vent_mode_rejected():
    with pytest.raises(ValueError, match="unknown vent.mode"):
        _resolve_vent_mode({"vent": {"mode": "bogus"}})


def test_none_mode_has_no_ventilator_demand():
    assert _vent_flags([1, 2], ["MICU", "SICU"], [9.0, 9.0], "none") == [False, False]


def test_pseudo_random_is_deterministic():
    first = _vent_flags([1, 2, 3, 4], ["MICU"] * 4, [0.0] * 4, "pseudo_random")
    second = _vent_flags([1, 2, 3, 4], ["MICU"] * 4, [0.0] * 4, "pseudo_random")
    assert first == second


def test_proxy_rule_requires_sofa_and_icu_unit():
    flags = _vent_flags(
        [1, 2, 3, 4],
        ["MICU", "CCU", "SICU", "MICU"],
        [6.0, 9.0, 4.0, 5.0],
        "proxy_rule",
        proxy_sofa_min=5,
    )
    assert flags == [True, False, False, True]


def test_real_mode_requires_flags():
    with pytest.raises(RuntimeError, match="feat.stay_flags"):
        _vent_flags([1], ["MICU"], [6.0], "real")


def test_real_mode_uses_supplied_flags():
    assert _vent_flags([1, 2], ["MICU", "CCU"], [6.0, 6.0], "real", real_flags=[True, False]) == [
        True,
        False,
    ]


def test_real_mode_length_mismatch():
    with pytest.raises(ValueError, match="length mismatch"):
        _vent_flags([1, 2], ["MICU", "CCU"], [6.0, 6.0], "real", real_flags=[True])
