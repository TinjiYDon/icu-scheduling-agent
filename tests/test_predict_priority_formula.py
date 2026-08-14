"""Unit tests for priority target construction helpers (no DB)."""

import numpy as np


def test_urgency_formula_monotone_in_sofa():
    def urgency(sofa: float, los: float) -> float:
        return 1.0 + sofa / 10.0 + 2.0 / (1.0 + max(los, 1.0))

    assert urgency(12, 24) > urgency(4, 24)
    assert urgency(8, 12) > urgency(8, 72)


def test_arrival_rate_clip():
    step = 2.0
    for mean_los in (10.0, 48.0, 200.0):
        rate = float(np.clip(step / max(mean_los, 1.0), 0.05, 0.35))
        assert 0.05 <= rate <= 0.35
