"""H10 前沿适配 / 滚动 HV–churn 单元测试：纯函数，无数据库/求解器/网络。"""

import numpy as np
import pytest

from domain.optimizer.pareto_io import (
    FrontSnapshot,
    hv_churn_series,
    normalize_points,
    parse_front,
    summarize_hv_churn,
)


# 1 — 裸矩阵 ----------------------------------------------------------------


def test_parse_matrix():
    points, ids = parse_front([[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]])
    assert points.shape == (3, 2)
    np.testing.assert_allclose(points[2], [0.5, 0.5])
    assert ids == ["sol_0", "sol_1", "sol_2"]


# 2 — moo_phase3 ObjectivePoint 风格 ---------------------------------------


def test_parse_objective_points_style():
    payload = {
        "points": [
            {"values": {"occupancy": 20, "wait": 5}, "source": "s1"},
            {"values": {"wait": 2, "occupancy": 18}, "source": "s2"},
        ]
    }
    points, ids = parse_front(payload)
    assert ids == ["s1", "s2"]
    # 键的并集排序：occupancy < wait
    np.testing.assert_allclose(points, [[20.0, 5.0], [18.0, 2.0]])

    # 显式 objectives 改列序
    points2, _ = parse_front(payload, objectives=["wait", "occupancy"])
    np.testing.assert_allclose(points2, [[5.0, 20.0], [2.0, 18.0]])

    # 裸 list[ObjectivePoint.as_dict()] 也支持
    points3, ids3 = parse_front(payload["points"])
    np.testing.assert_allclose(points3, points)
    assert ids3 == ["s1", "s2"]


def test_parse_ids_fallback_order():
    payload = {
        "points": [
            {"values": {"a": 1}, "name": "n0"},
            {"values": {"a": 2}, "id": "i1", "name": "n1"},
            {"values": {"a": 3}},
        ]
    }
    _, ids = parse_front(payload)
    assert ids == ["n0", "i1", "sol_2"]


# 3 — 扁平常量键 front ----------------------------------------------------


def test_parse_flat_front():
    payload = {"front": [{"f0": 0.8, "f1": 0.2}, {"f1": 0.9, "f0": 0.1}]}
    points, ids = parse_front(payload)
    np.testing.assert_allclose(points, [[0.8, 0.2], [0.1, 0.9]])
    assert ids == ["sol_0", "sol_1"]

    points2, _ = parse_front(payload, objectives=["f1", "f0"])
    np.testing.assert_allclose(points2, [[0.2, 0.8], [0.9, 0.1]])


# 4 — 错误输入 ------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"points": []},
        {"front": []},
        [1.0, 2.0],                      # 一维，非二维
        [[1.0, 2.0], [3.0]],             # 行列不一致
        {"points": [{"values": {"a": 1}}, {"values": {"b": 2}}]},  # 键不一致
        {"points": [{"values": {"a": 1}}, {"values": {"a": "x"}}]},  # 非数值
        {"nope": [[1.0]]},               # 未知 schema
        "not-a-front",
    ],
)
def test_parse_front_errors(payload):
    with pytest.raises(ValueError):
        parse_front(payload)


# 5 — 归一化 --------------------------------------------------------------


def test_normalize_points_bounds():
    pts = [[2.0, 10.0, 7.0], [4.0, 20.0, 7.0]]
    out = normalize_points(pts)
    np.testing.assert_allclose(out, [[0.0, 0.0, 1.0], [1.0, 1.0, 1.0]])

    explicit = normalize_points(pts, ideal=[4.0, 20.0, 7.0], nadir=[2.0, 10.0, 7.0])
    np.testing.assert_allclose(explicit, out)

    # 越界输入被 clip 到 [0,1]
    clipped = normalize_points([[0.0], [2.0]], ideal=[1.0], nadir=[0.0])
    np.testing.assert_allclose(clipped, [[0.0], [1.0]])


# 6 — 滚动序列 ------------------------------------------------------------


def _snapshot(step: int, ids: list[str], points: list[list[float]]) -> FrontSnapshot:
    return FrontSnapshot(step=step, ids=ids, points=normalize_points(points))


def test_hv_churn_series_three_steps():
    fronts = [
        _snapshot(0, ["a", "b"], [[0.5, 1.0], [1.0, 0.5]]),
        _snapshot(1, ["b", "c"], [[0.6, 1.0], [1.0, 0.7]]),
        _snapshot(2, ["c", "d"], [[0.4, 1.0], [1.0, 0.4]]),
    ]
    assignments = [
        {"p0": "b0", "p1": "b1", "p2": "b2"},
        {"p0": "b0", "p1": "b2", "p2": "b2"},
        {"p0": "b3", "p1": "b2", "p2": "b2"},
    ]
    series = hv_churn_series(fronts, assignments)

    assert [row["step"] for row in series] == [0, 1, 2]
    assert all(row["hv"] >= 0.0 for row in series)
    assert all(row["n_front"] == 2 for row in series)
    assert series[0]["turnover"] == 0.0 and series[0]["churn"] == 0.0
    for row in series[1:]:
        assert 0.0 <= row["turnover"] <= 1.0
        assert 0.0 <= row["churn"] <= 1.0

    # 第 1 步：{a,b} vs {b,c} → 1 - 1/3
    assert series[1]["turnover"] == pytest.approx(2 / 3, abs=1e-6)
    # 第 1 步：3 人共同，1 人换床 → 1/3
    assert series[1]["churn"] == pytest.approx(1 / 3, abs=1e-6)
    # 第 2 步：{b,c} vs {c,d} → 1 - 1/3
    assert series[2]["turnover"] == pytest.approx(2 / 3, abs=1e-6)
    assert series[2]["churn"] == pytest.approx(1 / 3, abs=1e-6)

    # 自定义 ref 降低 HV
    lower = hv_churn_series(fronts, assignments, ref=[0.5, 0.5])
    assert all(a["hv"] <= b["hv"] for a, b in zip(lower, series))


def test_hv_churn_series_accepts_plain_fronts_and_validates_length():
    series = hv_churn_series([[[1.0, 0.5], [0.5, 1.0]]], [{"p0": "b0"}])
    assert series[0]["hv"] == pytest.approx(0.75)

    with pytest.raises(ValueError):
        hv_churn_series([[[1.0, 0.5]]], [{}, {}])
    with pytest.raises(ValueError):
        hv_churn_series([[[1.0, 0.5]]], [{}], ref=[0.0, 0.0, 0.0])


# 7 — 汇总 ----------------------------------------------------------------


def test_summarize_hv_churn():
    series = [
        {"step": 0, "hv": 0.5, "n_front": 3, "turnover": 0.0, "churn": 0.0},
        {"step": 1, "hv": 0.75, "n_front": 4, "turnover": 0.5, "churn": 0.25},
        {"step": 2, "hv": 1.0, "n_front": 4, "turnover": 0.5, "churn": 0.25},
    ]
    summary = summarize_hv_churn(series)
    assert set(summary) == {
        "n_steps",
        "mean_hv",
        "total_churn",
        "mean_turnover",
        "last_hv",
    }
    assert summary["n_steps"] == 3
    assert summary["mean_hv"] == pytest.approx(0.75)
    assert summary["total_churn"] == pytest.approx(0.5)
    assert summary["mean_turnover"] == pytest.approx(1 / 3)
    assert summary["last_hv"] == pytest.approx(1.0)


def test_summarize_hv_churn_empty():
    assert summarize_hv_churn([]) == {
        "n_steps": 0,
        "mean_hv": 0.0,
        "total_churn": 0.0,
        "mean_turnover": 0.0,
        "last_hv": 0.0,
    }
