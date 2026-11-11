"""前沿质量指标：非支配前沿的“好不好看”的纯函数度量。

现有 `pareto_decision` 已能算超体积（HV）与决策层排序；本模块只补齐
**前沿形态**层面的三个常用指标，便于跨场景/跨策略对照：

- `hypervolume`：相对参考点支配的体积（越大越好，复用 `pareto_decision.hypervolume`）；
- `ideal / nadir / extent`：逐维最好/最差与覆盖范围（前沿张开的幅度）；
- `spacing` / `mean_pairwise`：点分布均匀程度（越小越均匀）。

约定：输入目标向量**全部为越大越好**（max 型），参考点缺省全 0。
不读数据库、不调求解器、不修改 `pareto_decision.py`。
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from domain.optimizer.pareto_decision import as_matrix, hypervolume

__all__ = ["front_quality"]


def _validate_points(points: Sequence[Sequence[float]]) -> np.ndarray:
    """形状 + 数值校验，返回 float 矩阵副本（不改调用方数据）。"""
    arr = np.asarray(points, dtype=float)
    if arr.size == 0:
        raise ValueError("points 不能为空：至少需要一个前沿点")
    mat = as_matrix(arr)
    if mat.shape[0] < 1 or mat.shape[1] < 1:
        raise ValueError("points 至少要有 1 个解、1 个目标维")
    if not np.all(np.isfinite(mat)):
        raise ValueError("points 含 NaN/Inf：前沿点必须是有限数值")
    return mat.copy()


def _validate_ref(ref: Sequence[float] | None, n_objectives: int) -> np.ndarray:
    """参考点校验：缺省全 0（与现有 HV 口径一致）。"""
    if ref is None:
        return np.zeros(n_objectives, dtype=float)
    r = np.asarray(ref, dtype=float)
    if r.ndim != 1:
        raise ValueError("ref 必须是一维向量 (n_objectives,)")
    if r.shape[0] != n_objectives:
        raise ValueError(
            f"ref 维数不匹配：ref={r.shape[0]} vs points 目标维={n_objectives}"
        )
    if not np.all(np.isfinite(r)):
        raise ValueError("ref 含 NaN/Inf：参考点必须是有限数值")
    return r.copy()


def _pairwise_distances(mat: np.ndarray) -> np.ndarray:
    """欧氏距离矩阵，对角为 inf（便于取最近邻）。"""
    diff = mat[:, None, :] - mat[None, :, :]
    dist = np.sqrt(np.sum(diff * diff, axis=-1))
    np.fill_diagonal(dist, np.inf)
    return dist


def front_quality(
    points: Sequence[Sequence[float]],
    ref: Sequence[float] | None = None,
) -> dict:
    """计算一个（非支配）前沿的质量指标。

    参数
    ----
    points : (n_points, n_objectives)，每维越大越好。
    ref : 参考点，缺省全 0；必须与 points 维数一致。

    返回
    ----
    dict，含 `n_points / n_objectives / hypervolume / ideal / nadir /
    extent / spacing / mean_pairwise`。

    `spacing` 是“每点到最近邻点欧氏距离”的均值（越小越均匀）；
    `mean_pairwise` 是全部点对距离均值（前沿整体分散程度）。
    只有 1 个点时两者均为 0.0。
    """
    mat = _validate_points(points)
    n_points, n_objectives = int(mat.shape[0]), int(mat.shape[1])
    ref_vec = _validate_ref(ref, n_objectives)

    ideal = mat.max(axis=0)
    nadir = mat.min(axis=0)

    if n_points == 1:
        spacing = 0.0
        mean_pairwise = 0.0
    else:
        dist = _pairwise_distances(mat)
        spacing = float(np.mean(np.min(dist, axis=1)))
        iu = np.triu_indices(n_points, k=1)
        mean_pairwise = float(np.mean(dist[iu]))

    return {
        "n_points": n_points,
        "n_objectives": n_objectives,
        "hypervolume": float(hypervolume(mat, ref_vec)),
        "ideal": [float(v) for v in ideal],
        "nadir": [float(v) for v in nadir],
        "extent": [float(v) for v in (ideal - nadir)],
        "spacing": spacing,
        "mean_pairwise": mean_pairwise,
    }
