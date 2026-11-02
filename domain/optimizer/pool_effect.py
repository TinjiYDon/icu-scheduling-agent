"""同池反事实：把“换池子”与“换机制”带来的增益拆开。

方法对照（H5 优先级消融 / H6 滚动再优化 / H7 RFCC 级联）里最常见的口径污染是：
对照方法跑在**不同的池**上（不同 stay 子集、不同入出转调度、不同资源上限），
于是“新机制更好”里混进了“池子更好”。同池反事实（matched pool）要求两组方法
在同一批 stay 上重跑，此时

    pool_effect = (metric_b^naive − metric_a^naive) − (metric_b^matched − metric_a^matched)

- `delta_naive`：整池上 b 相对 a 的变化（含池差）；
- `delta_match`：同池上 b 相对 a 的变化（纯机制差）；
- `pool_effect`：差值即“口径污染量”，> 0 说明整池口径高估了机制增益。

本模块只管代数，不做 IO、不跑求解器；`reports/*.json` 的数字由调用方喂进来。
"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np


def _num(value: Any, what: str) -> float:
    """有限实数校验（bool 不算数值）。"""
    if isinstance(value, bool):
        raise ValueError(f"{what} 必须是数值，收到 bool")
    if isinstance(value, np.ndarray):
        if value.size != 1:
            raise ValueError(f"{what} 必须是标量，收到 shape={value.shape}")
        value = value.reshape(-1)[0]
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{what} 必须是数值，收到 {value!r}") from exc
    if not np.isfinite(out):
        raise ValueError(f"{what} 含 NaN/Inf")
    return out


def pool_effect(
    naive_a: float,
    naive_b: float,
    matched_a: float,
    matched_b: float,
) -> dict:
    """同池反事实：返回两个 delta、`pool_effect` 与符号解释。

    - `naive_*`：整池（未匹配）下的指标；
    - `matched_*`：同一池子里重跑的指标；
    - `pool_effect = (naive_b − naive_a) − (matched_b − matched_a)`。
    """
    a_naive = _num(naive_a, "naive_a")
    b_naive = _num(naive_b, "naive_b")
    a_match = _num(matched_a, "matched_a")
    b_match = _num(matched_b, "matched_b")

    delta_naive = b_naive - a_naive
    delta_match = b_match - a_match
    effect = delta_naive - delta_match

    if abs(effect) <= 1e-12:
        sign = "zero"
        note = "整池口径与同池口径一致：未观察到池污染"
    elif effect > 0:
        sign = "positive"
        note = "整池口径高估了机制增益（池子本身更好）"
    else:
        sign = "negative"
        note = "整池口径低估了机制增益（池子本身更差）"

    return {
        "naive_a": a_naive,
        "naive_b": b_naive,
        "matched_a": a_match,
        "matched_b": b_match,
        "delta_naive": delta_naive,
        "delta_match": delta_match,
        "pool_effect": effect,
        "sign": sign,
        "interpretation": note,
    }


def decompose(
    delta_naive: float,
    delta_match: float,
    *,
    pool_gap_before: float | None = None,
    pool_gap_after: float | None = None,
) -> dict:
    """分解 delta，恒等式：`pool_effect + mechanism_effect + interaction = delta_naive`。

    记号：`pool_gap = metric_naive − metric_matched`（同一方法在两个池上的水平差）。

    - `mechanism_effect = delta_match`：同池内的机制增益；
    - `pool_effect = pool_gap_after − pool_gap_before`：池差漂移（若未给池差，
      等价于 `delta_naive − delta_match`）；
    - `interaction = delta_naive − mechanism_effect − pool_effect`：
      残差项。给出池差时它衡量“两个比较是否真的同池”（非线性指标、样本滑移、
      两套池子并不同源都会让它非零）；未给池差时恒为 0。
    """
    d_naive = _num(delta_naive, "delta_naive")
    d_match = _num(delta_match, "delta_match")

    if (pool_gap_before is None) != (pool_gap_after is None):
        raise ValueError("pool_gap_before 与 pool_gap_after 必须同时给出或都不给")

    if pool_gap_before is None:
        effect = d_naive - d_match
    else:
        before = _num(pool_gap_before, "pool_gap_before")
        after = _num(pool_gap_after, "pool_gap_after")
        effect = after - before

    mechanism = d_match
    interaction = d_naive - mechanism - effect
    if abs(interaction) <= 1e-12:
        interaction = 0.0

    return {
        "pool_effect": effect,
        "mechanism_effect": mechanism,
        "interaction": interaction,
    }


def summarize_pool_effect(results: Any) -> dict:
    """把多指标的同池反事实汇总成一张可读的表。"""
    if not isinstance(results, Mapping):
        raise ValueError(f"results 必须是字典，收到 {type(results).__name__}")
    if not results:
        raise ValueError("results 为空：至少需要 1 个指标")

    metrics: dict[str, float] = {}
    for name, value in results.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"results 的键必须是非空字符串，收到 {name!r}")
        if isinstance(value, Mapping):
            if "pool_effect" not in value:
                raise ValueError(f"results[{name}] 缺 pool_effect")
            effect = _num(value["pool_effect"], f"results[{name}].pool_effect")
        else:
            effect = _num(value, f"results[{name}]")
        metrics[name.strip()] = effect

    effects = list(metrics.values())
    abs_effects = [abs(x) for x in effects]
    n = len(effects)
    positive = sum(1 for x in effects if x > 1e-12)
    negative = sum(1 for x in effects if x < -1e-12)

    if positive and negative:
        dominant = "mixed"
    elif positive:
        dominant = "positive"
    elif negative:
        dominant = "negative"
    else:
        dominant = "zero"

    worst = max(metrics, key=lambda k: abs(metrics[k]))

    return {
        "n_metrics": n,
        "metrics": metrics,
        "mean_pool_effect": float(sum(effects) / n),
        "mean_abs_pool_effect": float(sum(abs_effects) / n),
        "max_abs_pool_effect": float(max(abs_effects)),
        "max_abs_metric": worst,
        "positive_share": float(positive / n),
        "dominant_sign": dominant,
    }


__all__ = ["pool_effect", "decompose", "summarize_pool_effect"]
