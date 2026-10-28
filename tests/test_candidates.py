from __future__ import annotations

import pytest

from domain.optimizer.cp_sat import _resolve_candidate_mode


def test_default_candidate_mode_is_top_score():
    assert _resolve_candidate_mode({}) == "top_score"


@pytest.mark.parametrize("mode", ["top_score", "fixed_sample", "stratified"])
def test_candidate_modes_are_accepted(mode):
    assert _resolve_candidate_mode({"candidates": {"mode": mode}}) == mode


def test_invalid_candidate_mode_rejected():
    with pytest.raises(ValueError, match="unknown candidates.mode"):
        _resolve_candidate_mode({"candidates": {"mode": "random"}})
