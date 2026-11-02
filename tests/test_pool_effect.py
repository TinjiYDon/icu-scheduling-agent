"""同池反事实（pool effect）单元测试：纯代数，无数据库/求解器/网络。"""

import numpy as np
import pytest

from domain.optimizer.pool_effect import decompose, pool_effect, summarize_pool_effect


# 1 — pool_effect 代数 ------------------------------------------------------


def test_pool_effect_algebra():
    out = pool_effect(0.40, 0.60, 0.42, 0.44)
    assert out["delta_naive"] == pytest.approx(0.20)
    assert out["delta_match"] == pytest.approx(0.02)
    assert out["pool_effect"] == pytest.approx(0.18)
    assert out["sign"] == "positive"
    assert out["pool_effect"] == pytest.approx(out["delta_naive"] - out["delta_match"])


def test_pool_effect_zero_and_negative():
    flat = pool_effect(1.0, 1.2, 0.5, 0.7)
    assert flat["pool_effect"] == pytest.approx(0.0)
    assert flat["sign"] == "zero"

    neg = pool_effect(0.6, 0.7, 0.2, 0.5)
    assert neg["pool_effect"] == pytest.approx(-0.2)
    assert neg["sign"] == "negative"

    arr = pool_effect(np.array([1.0]), 2.0, 1.0, 2.0)
    assert arr["pool_effect"] == pytest.approx(0.0)


# 2 — decompose 恒等 -------------------------------------------------------


def test_decompose_identity():
    out = decompose(0.20, 0.02)
    assert set(out) == {"pool_effect", "mechanism_effect", "interaction"}
    assert out["pool_effect"] + out["mechanism_effect"] + out["interaction"] == pytest.approx(0.20)
    assert out["pool_effect"] == pytest.approx(0.18)
    assert out["mechanism_effect"] == pytest.approx(0.02)
    assert out["interaction"] == pytest.approx(0.0)


def test_decompose_with_pool_gaps_detects_consistency():
    # 一致数据：gap 漂移恰好等于 delta_naive − delta_match → interaction = 0
    out = decompose(0.20, 0.02, pool_gap_before=0.30, pool_gap_after=0.48)
    assert out["pool_effect"] == pytest.approx(0.18)
    assert out["interaction"] == pytest.approx(0.0)

    # 不一致数据（两套池子不同源）→ interaction 非零
    off = decompose(0.20, 0.02, pool_gap_before=0.30, pool_gap_after=0.40)
    assert off["interaction"] == pytest.approx(0.08)
    total = off["pool_effect"] + off["mechanism_effect"] + off["interaction"]
    assert total == pytest.approx(0.20)

    with pytest.raises(ValueError):
        decompose(0.2, 0.1, pool_gap_before=0.3)


# 3 — summarize_pool_effect ------------------------------------------------


def test_summarize_pool_effect_keys():
    results = {
        "high_risk_wait": pool_effect(15, 4, 15, 6),
        "mean_avg_sofa": pool_effect(10.0, 10.1, 10.0, 10.05),
        "occupancy": 0.0,
    }
    out = summarize_pool_effect(results)
    for key in (
        "n_metrics",
        "metrics",
        "mean_pool_effect",
        "mean_abs_pool_effect",
        "max_abs_pool_effect",
        "max_abs_metric",
        "positive_share",
        "dominant_sign",
    ):
        assert key in out
    assert out["n_metrics"] == 3
    assert out["dominant_sign"] == "mixed"
    assert out["max_abs_metric"] == "high_risk_wait"
    assert out["max_abs_pool_effect"] == pytest.approx(2.0)
    assert out["mean_pool_effect"] == pytest.approx((-2.0 + 0.05 + 0.0) / 3)
    assert out["positive_share"] == pytest.approx(1 / 3)


def test_summarize_pool_effect_all_zero():
    out = summarize_pool_effect({"a": 0.0, "b": pool_effect(1, 1, 1, 1)})
    assert out["dominant_sign"] == "zero"
    assert out["mean_abs_pool_effect"] == pytest.approx(0.0)


# 4 — 非法输入 -------------------------------------------------------------


@pytest.mark.parametrize(
    "args",
    [
        (True, 1.0, 1.0, 1.0),
        ("x", 1.0, 1.0, 1.0),
        (float("nan"), 1.0, 1.0, 1.0),
        (1.0, 1.0, 1.0, np.array([1.0, 2.0])),
    ],
)
def test_pool_effect_invalid(args):
    with pytest.raises(ValueError):
        pool_effect(*args)


def test_summarize_and_decompose_invalid():
    with pytest.raises(ValueError):
        summarize_pool_effect({})
    with pytest.raises(ValueError):
        summarize_pool_effect([1.0])
    with pytest.raises(ValueError):
        summarize_pool_effect({"a": {"delta_naive": 1.0}})
    with pytest.raises(ValueError):
        decompose(float("inf"), 0.0)
