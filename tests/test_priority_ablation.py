from domain.scoring.priority_ablation import _spearman, _topk_overlap
import numpy as np


def test_spearman_identical():
    a = np.arange(10.0)
    assert abs(_spearman(a, a) - 1.0) < 1e-9


def test_topk_overlap_partial():
    a = np.array([5, 4, 3, 2, 1], dtype=float)
    b = np.array([5, 1, 4, 0, 0], dtype=float)
    assert _topk_overlap(a, b, k=2) == 0.5
