"""Candidate counts requested by experiments must reach the environment loader."""

import pytest

from domain.rl import factory
from domain.rl.env import Bed, Patient


def test_explicit_candidate_count_overrides_twenty_patient_default(monkeypatch):
    monkeypatch.setattr(factory, "load_yaml", lambda _: {"ppo": {"candidate_patients": 20}})
    requested = []

    def patients(limit):
        requested.append(limit)
        return [Patient(i, 1) for i in range(limit)]

    monkeypatch.setattr(factory, "load_patients", patients)
    monkeypatch.setattr(factory, "load_beds", lambda _: [Bed(1)])
    env = factory.build_icu_env(candidate_patients=40)
    assert requested == [40]
    assert len(env.patients) == 40


@pytest.mark.parametrize("entry", ["bakeoff", "pto"])
def test_experiments_forward_requested_candidate_count(monkeypatch, entry):
    from application.run_method_bakeoff import run_method_bakeoff
    from application.run_pto_ablation import run_pto_ablation

    class PoolSelected(Exception):
        pass

    def select_pool(**kwargs):
        assert kwargs["candidate_patients"] == 40
        raise PoolSelected

    monkeypatch.setattr(factory, "build_icu_env", select_pool)
    with pytest.raises(PoolSelected):
        (run_method_bakeoff if entry == "bakeoff" else run_pto_ablation)(candidate_patients=40)
