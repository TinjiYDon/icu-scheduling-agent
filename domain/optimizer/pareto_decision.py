"""H10 · Pareto 决策层：前沿价值（VoF）与偏好稳健排序（MMR）。

现有 `moo_phase3` 已经能做非支配过滤 + 精确超体积；本模块**不重复**前沿生成，
而是在给定前沿上回答“选哪个、值多少钱、滚动稳不稳”：

- VoF（Value of Frontier）：偏好不确定时，前沿比单一固定权重解多值多少钱；
- CoM（Cost of Misspecification）：固定解选错的期望后悔；
- MMR（Minimax Regret）：按最坏偏好下的后悔给前沿排序；
- HV / churn / front turnover：滚动重解的稳定性指标。

约定：输入的目标向量已归一化且**全部为越大越好**（max 型）。
不读数据库、不调求解器；求解器输出由调用方注入。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from domain.optimizer.moo_phase3 import _hv_exact


def as_matrix(points: Sequence[Sequence[float]]) -> np.ndarray:
    arr = np.asarray(points, dtype=float)
    if arr.ndim != 2:
        raise ValueError("points 必须是二维矩阵 (n_solutions, n_objectives)")
    return arr


def dominates(a: Sequence[float], b: Sequence[float]) -> bool:
    """a 支配 b（全部最大化）：每维不差，且至少一维更好。"""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    return bool(np.all(a >= b) and np.any(a > b))


def nondominated_indices(points: Sequence[Sequence[float]]) -> list[int]:
    """返回非支配解的索引（保留输入顺序）。"""
    mat = as_matrix(points)
    keep: list[int] = []
    for i, p in enumerate(mat):
        if not any(dominates(q, p) for j, q in enumerate(mat) if j != i):
            keep.append(i)
    return keep


def normalize_front(
    values: Sequence[Sequence[float]],
    ideal: Sequence[float],
    nadir: Sequence[float],
) -> np.ndarray:
    """把每维线性映射到 [0,1]（1=理想），用于 HV/VoF 的可比计算。"""
    v = as_matrix(values)
    ideal = np.asarray(ideal, dtype=float)
    nadir = np.asarray(nadir, dtype=float)
    span = np.where(np.abs(ideal - nadir) > 1e-12, ideal - nadir, 1.0)
    return np.clip((v - nadir) / span, 0.0, 1.0)


def hypervolume(points: Sequence[Sequence[float]], ref: Sequence[float]) -> float:
    """精确超体积（复用 moo_phase3 的递归实现；全部最大化）。"""
    mat = as_matrix(points)
    return float(_hv_exact([tuple(map(float, row)) for row in mat],
                           tuple(map(float, ref))))


def simplex_weights(n_samples: int, n_objectives: int, seed: int = 0) -> np.ndarray:
    """在单纯形上采样偏好权重（Dirichlet(1,...,1)）。"""
    rng = np.random.default_rng(seed)
    return rng.dirichlet(np.ones(n_objectives), size=n_samples)


def _costs(front: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """c(x;w) = -w·f(x)（越小越好），返回 (n_solutions, n_weights)。"""
    return -(front @ weights.T)


def value_of_front(
    front: Sequence[Sequence[float]],
    single: Sequence[float],
    weights: Sequence[Sequence[float]],
) -> dict:
    """前沿价值：oracle 选择 vs 单一固定解。

    - VoF = E_w[c(single;w) − min_x c(x;w)]
    - CoM = max_w[c(single;w) − min_x c(x;w)]（最坏偏好下的后悔）
    - regret_matrix: 每个解在每个偏好下的后悔
    """
    f = as_matrix(front)
    w = as_matrix(weights)
    single = np.asarray(single, dtype=float)
    if f.shape[1] != single.shape[0] or f.shape[1] != w.shape[1]:
        raise ValueError("front / single / weights 的目标维数不一致")
    cost = _costs(f, w)                      # (n, s)
    oracle = cost.min(axis=0)                # (s,)
    single_cost = -(single @ w.T)            # (s,)
    regret = cost - oracle                   # (n, s)
    single_regret = single_cost - oracle
    vof = float(np.mean(single_regret))
    com = float(np.max(single_regret))
    return {
        "n_front": int(f.shape[0]),
        "n_weights": int(w.shape[0]),
        "VoF": round(vof, 6),
        "CoM": round(com, 6),
        "oracle_mean_cost": round(float(np.mean(oracle)), 6),
        "single_mean_cost": round(float(np.mean(single_cost)), 6),
        "regret_matrix": regret,
    }


def expected_regret(
    front: Sequence[Sequence[float]],
    weights: Sequence[Sequence[float]],
    solution_index: int,
) -> float:
    f, w = as_matrix(front), as_matrix(weights)
    cost = _costs(f, w)
    oracle = cost.min(axis=0)
    return float(np.mean(cost[solution_index] - oracle))


def minimax_regret_ranking(
    front: Sequence[Sequence[float]],
    weights: Sequence[Sequence[float]],
) -> list[dict]:
    """按最大后悔升序排序：第 1 个是对最坏偏好最稳的解。"""
    f, w = as_matrix(front), as_matrix(weights)
    cost = _costs(f, w)
    oracle = cost.min(axis=0)
    regret = cost - oracle
    worst = regret.max(axis=1)
    order = np.argsort(worst)
    return [
        {"index": int(i), "max_regret": round(float(worst[i]), 6),
         "mean_regret": round(float(regret[i].mean()), 6)}
        for i in order
    ]


def front_turnover(ids_t: Sequence[str], ids_t1: Sequence[str]) -> float:
    """相邻两步非支配集周转率：1 − |交集| / |并集|。"""
    a, b = set(ids_t), set(ids_t1)
    union = a | b
    if not union:
        return 0.0
    return round(1.0 - len(a & b) / len(union), 6)


def assignment_churn(assign_t: dict[str, str], assign_t1: dict[str, str]) -> float:
    """相邻两步换床率：换床人数 / 两期都出现的患者数。"""
    common = set(assign_t) & set(assign_t1)
    if not common:
        return 0.0
    moved = sum(1 for k in common if assign_t[k] != assign_t1[k])
    return round(moved / len(common), 6)


@dataclass
class FrontSummary:
    n_front: int
    n_objectives: int
    hypervolume: float
    VoF: float
    CoM: float
    mmr_top: list[dict]

    def as_dict(self) -> dict:
        return {
            "n_front": self.n_front,
            "n_objectives": self.n_objectives,
            "hypervolume": self.hypervolume,
            "VoF": self.VoF,
            "CoM": self.CoM,
            "mmr_top": self.mmr_top,
        }


def summarize_front(
    front: Sequence[Sequence[float]],
    single: Sequence[float],
    weights: Sequence[Sequence[float]],
    ref: Sequence[float] | None = None,
) -> FrontSummary:
    f = as_matrix(front)
    ref = ref if ref is not None else tuple([0.0] * f.shape[1])
    vof = value_of_front(f, single, weights)
    return FrontSummary(
        n_front=int(f.shape[0]),
        n_objectives=int(f.shape[1]),
        hypervolume=round(hypervolume(f, ref), 6),
        VoF=vof["VoF"],
        CoM=vof["CoM"],
        mmr_top=minimax_regret_ranking(f, weights)[:5],
    )
