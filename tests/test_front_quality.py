"""前沿质量指标单元测试：纯函数，无数据库 / 无求解器。"""

import math

import numpy as np
import pytest

from domain.optimizer.front_quality import front_quality
from domain.optimizer.pareto_decision import hypervolume

FRONT = [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]]


def test_keys_and_shapes():
    q = front_quality(FRONT)
    assert set(q) == {
        "n_points",
        "n_objectives",
        "hypervolume",
        "ideal",
        "nadir",
        "extent",
        "spacing",
        "mean_pairwise",
    }
    assert q["n_points"] == 3
    assert q["n_objectives"] == 2
    assert isinstance(q["n_points"], int) and isinstance(q["n_objectives"], int)
    assert isinstance(q["ideal"], list) and isinstance(q["nadir"], list)
    assert isinstance(q["extent"], list)


def test_ideal_nadir_extent_max_sense():
    q = front_quality(FRONT)
    assert q["ideal"] == [1.0, 1.0]
    assert q["nadir"] == [0.0, 0.0]
    assert q["extent"] == [1.0, 1.0]

    q2 = front_quality([[2.0, 10.0], [4.0, 6.0]])
    assert q2["ideal"] == [4.0, 10.0]
    assert q2["nadir"] == [2.0, 6.0]
    assert q2["extent"] == [2.0, 4.0]


def test_extent_zero_for_single_point():
    q = front_quality([[3.0, 7.0]])
    assert q["extent"] == [0.0, 0.0]
    assert q["ideal"] == [3.0, 7.0]
    assert q["nadir"] == [3.0, 7.0]


def test_hypervolume_matches_pareto_decision():
    q = front_quality(FRONT)
    assert q["hypervolume"] == pytest.approx(hypervolume(FRONT, [0.0, 0.0]))
    assert q["hypervolume"] > 0.0
    # 经典两矩形：0.5 + 0.25
    assert front_quality([[0.5, 1.0], [1.0, 0.5]])["hypervolume"] == pytest.approx(0.75)


def test_hypervolume_default_ref_is_zero():
    q = front_quality([[1.0, 2.0]])
    assert q["hypervolume"] == pytest.approx(2.0)


def test_hypervolume_custom_ref():
    pts = [[2.0, 2.0], [4.0, 1.0]]
    q = front_quality(pts, ref=[1.0, 1.0])
    assert q["hypervolume"] == pytest.approx(hypervolume(pts, [1.0, 1.0]))
    # 手算：矩形 [1,2]x[1,2] = 1*1，另加 [2,4]x[1,1] 高度 0 -> 合计 1.0？用 [1,4]x[1,1] 无高
    # 实际支配区域：(x-1)*(min(2,f2)-1) 分片：x∈[1,2]: h=1 -> 1.0；x∈[2,4]: h=0 -> 0
    assert q["hypervolume"] == pytest.approx(1.0)
    # 换一个参考点，HV 单调不降/不升：抬高 ref 只能让体积变小
    assert front_quality(pts, ref=[0.0, 0.0])["hypervolume"] >= q["hypervolume"]


def test_hypervolume_1d():
    q = front_quality([[1.0], [3.0]])
    assert q["n_objectives"] == 1
    assert q["hypervolume"] == pytest.approx(3.0)
    assert q["extent"] == [2.0]
    assert q["spacing"] == pytest.approx(2.0)
    assert q["mean_pairwise"] == pytest.approx(2.0)


def test_spacing_and_mean_pairwise_analytic():
    q = front_quality(FRONT)
    # 三点两两距离：sqrt2, sqrt(0.5), sqrt(0.5)；每点最近邻都是 sqrt(0.5)
    assert q["spacing"] == pytest.approx(math.sqrt(0.5))
    assert q["mean_pairwise"] == pytest.approx(2.0 * math.sqrt(2.0) / 3.0)


def test_spacing_uniform_line_and_scale_dependence():
    # 等距三点：spacing = 最近邻距离均值 = 步长; mean_pairwise = (1+1+2)/3
    uniform = [[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]]
    qu = front_quality(uniform)
    assert qu["spacing"] == pytest.approx(1.0)
    assert qu["mean_pairwise"] == pytest.approx(4.0 / 3.0)

    # spacing 是绝对值，随前沿尺度线性缩放（未做 extent 归一化）
    compressed = [[0.0, 0.0], [0.5, 0.0], [1.0, 0.0]]
    qc = front_quality(compressed)
    assert qc["spacing"] == pytest.approx(0.5)
    assert qc["mean_pairwise"] == pytest.approx(2.0 / 3.0)


def test_single_point_spacing_zero():
    q = front_quality([[1.0, 1.0]])
    assert q["spacing"] == 0.0
    assert q["mean_pairwise"] == 0.0


def test_duplicate_points_have_zero_spacing():
    q = front_quality([[1.0, 1.0], [1.0, 1.0]])
    assert q["spacing"] == 0.0
    assert q["mean_pairwise"] == 0.0
    assert q["hypervolume"] == pytest.approx(1.0)


def test_accepts_numpy_and_mixed_nested():
    mat = np.array(FRONT)
    assert front_quality(mat) == front_quality(FRONT)
    assert front_quality([(1, 0), (0, 1), (0.5, 0.5)]) == front_quality(FRONT)


def test_does_not_mutate_input():
    pts = [[1.0, 0.0], [0.0, 1.0]]
    snapshot = [list(p) for p in pts]
    front_quality(pts)
    assert pts == snapshot

    arr = np.array([[1.0, 0.0], [0.0, 1.0]])
    arr_snapshot = arr.copy()
    front_quality(arr)
    np.testing.assert_array_equal(arr, arr_snapshot)


def test_three_objectives_smoke():
    q = front_quality([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    assert q["n_objectives"] == 3
    assert q["ideal"] == [1.0, 1.0, 1.0]
    assert q["nadir"] == [0.0, 0.0, 0.0]
    # 三维单位轴点的支配盒体积为 0（退化），这是 HV 的正常语义
    assert q["hypervolume"] == pytest.approx(0.0)
    assert q["spacing"] == pytest.approx(math.sqrt(2.0))
    assert q["mean_pairwise"] == pytest.approx(math.sqrt(2.0))


def test_three_objectives_non_degenerate_hypervolume():
    pts = [[1.0, 1.0, 0.5], [1.0, 0.5, 1.0], [0.5, 1.0, 1.0]]
    q = front_quality(pts)
    assert q["hypervolume"] == pytest.approx(hypervolume(pts, [0.0, 0.0, 0.0]))
    assert q["hypervolume"] == pytest.approx(0.875)
    assert q["extent"] == pytest.approx([0.5, 0.5, 0.5])


@pytest.mark.parametrize(
    "bad",
    [
        [],
        (),
        [[]],
        [[], []],
    ],
)
def test_empty_front_raises(bad):
    with pytest.raises(ValueError):
        front_quality(bad)


@pytest.mark.parametrize(
    "bad",
    [
        [1.0, 2.0],  # 1D
        [[[1.0, 2.0], [3.0, 4.0]]],  # 3D
    ],
)
def test_wrong_dimensionality_raises(bad):
    with pytest.raises(ValueError):
        front_quality(bad)


@pytest.mark.parametrize(
    "bad_value",
    [float("nan"), float("inf"), float("-inf")],
)
def test_non_finite_points_raise(bad_value):
    with pytest.raises(ValueError):
        front_quality([[1.0, 0.0], [bad_value, 1.0]])


@pytest.mark.parametrize(
    "bad_ref",
    [[0.0], [0.0, 0.0, 0.0], 0.0, [[0.0, 0.0]]],
)
def test_ref_dimension_mismatch_raises(bad_ref):
    with pytest.raises(ValueError):
        front_quality(FRONT, ref=bad_ref)


def test_non_finite_ref_raises():
    with pytest.raises(ValueError):
        front_quality(FRONT, ref=[0.0, float("nan")])


def test_type_error_on_non_numeric():
    with pytest.raises((ValueError, TypeError)):
        front_quality([["a", "b"]])
