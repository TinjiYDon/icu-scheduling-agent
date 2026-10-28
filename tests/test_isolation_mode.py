from __future__ import annotations

import pytest

from domain.optimizer.cp_sat import _iso_flags, _resolve_iso_mode


def test_default_mode_is_none():
    assert _resolve_iso_mode({}) == "none"


def test_mode_from_config():
    assert _resolve_iso_mode({"isolation": {"mode": "careunit_keyword"}}) == "careunit_keyword"
    assert _resolve_iso_mode({"isolation": {"mode": "real"}}) == "real"


def test_invalid_mode_rejected():
    with pytest.raises(ValueError, match="unknown isolation.mode"):
        _resolve_iso_mode({"isolation": {"mode": "bogus"}})


def test_none_mode_has_no_isolation():
    careunits = ["Medical Intensive Care Unit (MICU)", None]
    assert _iso_flags(careunits, "none") == [False, False]


def test_keyword_mode_flags_icu_units():
    careunits = [
        "Medical Intensive Care Unit (MICU)",
        "Surgical Intensive Care Unit (SICU)",
        "Trauma SICU (TSICU)",
        "Coronary Care Unit (CCU)",
        "Neuro Intermediate",
    ]
    assert _iso_flags(careunits, "careunit_keyword") == [True, True, True, False, False]


def test_real_mode_requires_flags():
    with pytest.raises(RuntimeError, match="feat.stay_flags"):
        _iso_flags(["MICU"], "real")


def test_real_mode_uses_supplied_flags():
    assert _iso_flags(["MICU", "CCU"], "real", [True, False]) == [True, False]


def test_real_mode_length_mismatch():
    with pytest.raises(ValueError, match="length mismatch"):
        _iso_flags(["MICU", "CCU"], "real", [True])
