from __future__ import annotations

from domain.rl.env import Bed, ICUEnv, Patient
from domain.rl.evaluation import evaluate_greedy


def test_greedy_prefers_matching_legal_zone():
    env = ICUEnv(
        patients=[Patient(1, 2.0, preferred_zone="SICU")],
        beds=[Bed(1, "MICU"), Bed(2, "SICU")],
    )

    result = evaluate_greedy(env)

    assert result["assignments"][0]["bed_id"] == 2
