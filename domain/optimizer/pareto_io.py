"""H10 · 前沿适配 + 滚动 HV–churn。

`moo_phase3`（内部 `ObjectivePoint` 列表）、外部 JSON、以及裸矩阵三种前沿 schema
互不统一，滚动评估前必须先落到同一个结构：

- `parse_front(payload, objectives=None)` → `(points, ids)`：只做解析 + 对齐，
  **不做归一化**（归一化交给 `normalize_points`）；
- `normalize_points(points, ideal, nadir)`：全部**越大越好**，线性映射到 [0,1]；
- `hv_churn_series(fronts, assignments, ref)`：逐步算 HV / 前沿周转 / 换床率；
- `summarize_hv_churn(series)`：整段滚动汇总。

约定：目标向量全部为 max 型；不读数据库、不跑求解器、不访问网络。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from domain.optimizer.pareto_decision import (
    assignment_churn,
    front_turnover,
    hypervolume,
)

_ID_KEYS = ("source", "id", "name")


@dataclass(frozen=True)
class FrontSnapshot:
    """一步前沿：`points` 已归一化且全部越大越好，`ids` 与行一一对应。"""

    step: int
    ids: list[str]
    points: np.ndarray
    raw: list[dict] | None = None

    def as_dict(self) -> dict:
        return {
            "step": int(self.step),
            "ids": list(self.ids),
            "points": [[round(float(x), 6) for x in row] for row in np.asarray(self.points)],
        }


def _as_matrix(rows: Sequence[Sequence[float]], what: str = "payload") -> np.ndarray:
    """把“等长数值行”的序列转成 (n, m) 浮点矩阵；不规则/空 → ValueError。"""
    if isinstance(rows, np.ndarray):
        rows = list(rows)
    if not isinstance(rows, (list, tuple)):
        raise ValueError(f"{what} 必须是非空的行序列，收到 {type(rows).__name__}")
    if len(rows) == 0:
        raise ValueError(f"{what} 为空：至少需要 1 行")

    width = None
    out: list[list[float]] = []
    for i, row in enumerate(rows):
        if isinstance(row, np.ndarray):
            row = list(row)
        if not isinstance(row, (list, tuple)):
            raise ValueError(f"{what}[{i}] 不是行向量（收到 {type(row).__name__}）")
        if width is None:
            width = len(row)
        elif len(row) != width:
            raise ValueError(
                f"{what}[{i}] 列数 {len(row)} 与首行 {width} 不一致（行列不一致）"
            )
        try:
            out.append([float(v) for v in row])
        except (TypeError, ValueError) as exc:  # 非数值
            raise ValueError(f"{what}[{i}] 含非数值元素：{exc}") from exc
    if width == 0:
        raise ValueError(f"{what} 每行为空：至少需要 1 个目标维")

    arr = np.asarray(out, dtype=float)
    if arr.ndim != 2:
        raise ValueError("points 必须是二维矩阵 (n_solutions, n_objectives)")
    if not np.all(np.isfinite(arr)):
        raise ValueError("points 含 NaN/Inf")
    return arr


def _row_id(row: Mapping[str, Any], index: int) -> str:
    for key in _ID_KEYS:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f"sol_{index}"


def _values_matrix(
    rows: Sequence[Mapping[str, Any]],
    objectives: Sequence[str] | None,
    what: str,
) -> tuple[np.ndarray, list[str], list[str]]:
    """从“扁平/带 values 的字典行”抽矩阵；返回 (matrix, ids, 目标名)。"""
    if not isinstance(rows, (list, tuple)) or len(rows) == 0:
        raise ValueError(f"{what} 为空：至少需要 1 个解")
    if not all(isinstance(r, Mapping) for r in rows):
        raise ValueError(f"{what} 的每一行必须是字典")

    flat = [_flatten_row(r, what) for r in rows]

    if objectives:
        names = [str(o) for o in objectives]
        missing = sorted({n for row in flat for n in names if n not in row})
        if missing:
            raise ValueError(f"{what} 缺目标键：{missing}")
    else:
        union: set[str] = set()
        for row in flat:
            union.update(row)
        names = sorted(union)
    if not names:
        raise ValueError(f"{what} 没有任何目标键")

    for i, row in enumerate(flat):
        missing = [n for n in names if n not in row]
        if missing:
            raise ValueError(f"{what}[{i}] 缺目标键 {missing}（行列不一致）")

    matrix = _as_matrix([[row[n] for n in names] for row in flat], what)
    ids = [_row_id(raw, i) for i, raw in enumerate(rows)]
    return matrix, ids, names


def _flatten_row(row: Mapping[str, Any], what: str) -> dict[str, Any]:
    """`ObjectivePoint.as_dict()` 风格（含 `values`）拍平；否则视为常量键行。"""
    values = row.get("values")
    if isinstance(values, Mapping):
        return dict(values)
    return {k: v for k, v in row.items() if k not in _ID_KEYS and k != "values"}


def parse_front(
    payload: Any,
    objectives: Sequence[str] | None = None,
) -> tuple[np.ndarray, list[str]]:
    """把三种前沿 schema 解析为 `(points, ids)`（未归一化，全部越大越好）。

    支持：

    1. `list[list[float]]`：每行一个解；
    2. `{"points": [{"values": {...}, "source": "s1"}, ...]}`（moo_phase3 风格；
       也接受裸的 `list[ObjectivePoint.as_dict()]`）；
    3. `{"front": [{"f0": 0.8, "f1": 0.2}, ...]}`（扁平常量键）。

    `objectives` 给定时按其顺序取列；否则取所有行键的并集排序。
    ids 优先 `source` / `id` / `name`，否则 `sol_<index>`。
    """
    if isinstance(payload, np.ndarray):
        payload = payload.tolist()

    if isinstance(payload, (list, tuple)):
        if len(payload) == 0:
            raise ValueError("payload 为空：至少需要 1 个解")
        if all(isinstance(r, Mapping) for r in payload):
            matrix, ids, _ = _values_matrix(payload, objectives, "payload")
            return matrix, ids
        return _as_matrix(payload, "payload"), [f"sol_{i}" for i in range(len(payload))]

    if isinstance(payload, Mapping):
        rows = None
        what = "payload"
        for key in ("points", "front"):
            if key in payload:
                rows = payload[key]
                what = f"payload[{key!r}]"
                break
        if rows is None:
            raise ValueError("payload 字典必须含 'points' 或 'front' 键")
        if isinstance(rows, np.ndarray):
            rows = rows.tolist()
        if not isinstance(rows, (list, tuple)):
            raise ValueError(f"{what} 必须是列表")
        if len(rows) == 0:
            raise ValueError(f"{what} 为空：至少需要 1 个解")
        if all(isinstance(r, Mapping) for r in rows):
            matrix, ids, _ = _values_matrix(rows, objectives, what)
            return matrix, ids
        matrix = _as_matrix(rows, what)
        if objectives and len(objectives) != matrix.shape[1]:
            raise ValueError(
                f"objectives 数量 {len(objectives)} 与列数 {matrix.shape[1]} 不一致"
            )
        return matrix, [f"sol_{i}" for i in range(matrix.shape[0])]

    raise ValueError(f"不支持的 payload 类型：{type(payload).__name__}")


def normalize_points(
    points: Sequence[Sequence[float]] | np.ndarray,
    ideal: Sequence[float] | None = None,
    nadir: Sequence[float] | None = None,
) -> np.ndarray:
    """全部最大化：线性映射到 [0,1] 并 clip；`ideal == nadir` 的维恒为 1.0。

    默认 `ideal = points.max(axis=0)`、`nadir = points.min(axis=0)`。
    """
    mat = _as_matrix(points, "points")
    hi = mat.max(axis=0) if ideal is None else np.asarray(ideal, dtype=float)
    lo = mat.min(axis=0) if nadir is None else np.asarray(nadir, dtype=float)
    if hi.shape != (mat.shape[1],) or lo.shape != (mat.shape[1],):
        raise ValueError(
            f"ideal/nadir 维数应为 {mat.shape[1]}，收到 {hi.shape} / {lo.shape}"
        )

    span = hi - lo
    const = np.abs(span) <= 1e-12
    safe_span = np.where(const, 1.0, span)
    out = (mat - lo) / safe_span
    out = np.where(const, 1.0, out)
    return np.clip(out, 0.0, 1.0)


def _front_matrix(front: Any, index: int) -> np.ndarray:
    if isinstance(front, FrontSnapshot):
        return _as_matrix(front.points, f"fronts[{index}].points")
    if isinstance(front, Mapping) and "points" in front:
        return _as_matrix(front["points"], f"fronts[{index}].points")
    if isinstance(front, (list, tuple, np.ndarray)):
        return _as_matrix(front, f"fronts[{index}]")
    raise ValueError(f"fronts[{index}] 无法解析为前沿")


def _front_ids(front: Any, index: int, n_rows: int) -> list[str]:
    ids = getattr(front, "ids", None)
    if ids is None and isinstance(front, Mapping):
        ids = front.get("ids")
    if ids is None:
        return [f"sol_{i}" for i in range(n_rows)]
    ids = [str(x) for x in ids]
    if len(ids) != n_rows:
        raise ValueError(f"fronts[{index}].ids 长度 {len(ids)} 与点数 {n_rows} 不一致")
    return ids


def _front_step(front: Any, index: int) -> int:
    step = getattr(front, "step", None)
    if step is None and isinstance(front, Mapping):
        step = front.get("step")
    return index if step is None else int(step)


def hv_churn_series(
    fronts: Sequence[Any],
    assignments: Sequence[Mapping[str, str]],
    ref: Sequence[float] | None = None,
) -> list[dict]:
    """滚动指标序列：每步 HV + 前沿周转 + 换床率。

    - `hv = hypervolume(front.points, ref)`（`ref` 默认全 0）；
    - `turnover = front_turnover(ids_{t-1}, ids_t)`，首步 0.0；
    - `churn = assignment_churn(assign_{t-1}, assign_t)`，首步 0.0。
    """
    if len(fronts) != len(assignments):
        raise ValueError(
            f"fronts 长度 {len(fronts)} 与 assignments 长度 {len(assignments)} 不一致"
        )

    series: list[dict] = []
    prev_ids: list[str] | None = None
    prev_assign: Mapping[str, str] | None = None
    for index, (front, assign) in enumerate(zip(fronts, assignments)):
        mat = _front_matrix(front, index)
        ids = _front_ids(front, index, mat.shape[0])
        if not isinstance(assign, Mapping):
            raise ValueError(f"assignments[{index}] 必须是 dict[patient_id, bed_id]")

        step_ref = ref if ref is not None else tuple([0.0] * mat.shape[1])
        ref_dim = len(tuple(step_ref))
        if ref_dim != mat.shape[1]:
            raise ValueError(
                f"ref 维数 {ref_dim} 与 fronts[{index}] 目标维数 {mat.shape[1]} 不一致"
            )
        hv = hypervolume(mat, step_ref)

        turnover = 0.0 if prev_ids is None else front_turnover(prev_ids, ids)
        churn = (
            0.0
            if prev_assign is None
            else assignment_churn(dict(prev_assign), dict(assign))
        )

        series.append(
            {
                "step": _front_step(front, index),
                "hv": round(float(hv), 6),
                "n_front": int(mat.shape[0]),
                "turnover": round(float(turnover), 6),
                "churn": round(float(churn), 6),
            }
        )
        prev_ids, prev_assign = ids, assign
    return series


def summarize_hv_churn(series: Sequence[Mapping[str, Any]]) -> dict:
    """汇总滚动序列：步数 / 平均 HV / 累积换床 / 平均周转 / 末步 HV。"""
    n_steps = len(series)
    if n_steps == 0:
        return {
            "n_steps": 0,
            "mean_hv": 0.0,
            "total_churn": 0.0,
            "mean_turnover": 0.0,
            "last_hv": 0.0,
        }
    hv = [float(row["hv"]) for row in series]
    churn = [float(row["churn"]) for row in series]
    turnover = [float(row["turnover"]) for row in series]
    return {
        "n_steps": int(n_steps),
        "mean_hv": round(float(np.mean(hv)), 6),
        "total_churn": round(float(np.sum(churn)), 6),
        "mean_turnover": round(float(np.mean(turnover)), 6),
        "last_hv": round(float(hv[-1]), 6),
    }
