"""H10 Pareto 决策层单元测试：纯函数，无数据库/求解器。"""

import numpy as np
import pytest

from domain.optimizer.pareto_decision import (
    assignment_churn,
    dominates,
    front_turnover,
    hypervolume,
    minimax_regret_ranking,
    nondominated_indices,
    normalize_front,
    simplex_weights,
    summarize_front,
    value_of_front,
)


def test_dominates():
    assert dominates([1.0, 1.0], [0.5, 0.5])
    assert not dominates([1.0, 0.5], [0.5, 1.0])
    assert not dominates([1.0, 1.0], [1.0, 1.0])


def test_nondominated_indices():
    pts = [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5], [0.2, 0.2]]
    keep = nondominated_indices(pts)
    assert keep == [0, 1, 2]


def test_hypervolume_2d():
    # 两个矩形：[0,0.5]x[0,1] 与 [0.5,1]x[0,0.5] -> 0.5 + 0.25
    hv = hypervolume([[0.5, 1.0], [1.0, 0.5]], [0.0, 0.0])
    assert hv == 0.75


def test_normalize_front():
    out = normalize_front([[2.0, 10.0], [4.0, 20.0]], ideal=[4.0, 20.0], nadir=[2.0, 10.0])
    np.testing.assert_allclose(out, [[0.0, 0.0], [1.0, 1.0]])


def test_value_of_front_positive_when_front_dominates_single():
    front = [[1.0, 0.5], [0.5, 1.0], [0.6, 0.6]]
    single = [0.5, 0.5]
    w = simplex_weights(200, 2, seed=0)
    out = value_of_front(front, single, w)
    assert out["VoF"] > 0
    assert out["CoM"] >= out["VoF"]


def test_mmr_prefers_balanced_solution():
    front = [[1.0, 0.0], [0.0, 1.0], [0.6, 0.6]]
    w = np.array([[0.5, 0.5]])
    ranking = minimax_regret_ranking(front, w)
    assert ranking[0]["index"] == 2


def test_turnover_and_churn():
    assert front_turnover(["a", "b"], ["b", "c"]) == pytest.approx(2 / 3, abs=1e-6)
    assert assignment_churn({"p1": "b1", "p2": "b2"}, {"p1": "b1", "p2": "b3"}) == 0.5


def test_summarize_front():
    front = [[1.0, 0.2], [0.4, 1.0], [0.6, 0.6]]
    w = simplex_weights(100, 2, seed=1)
    s = summarize_front(front, [0.5, 0.5], w)
    d = s.as_dict()
    assert d["n_front"] == 3
    assert d["hypervolume"] > 0
    assert d["VoF"] >= 0
    assert len(d["mmr_top"]) == 3
