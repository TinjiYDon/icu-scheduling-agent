"""FD 压测：伪自由度（spurious DoF）与契约对齐度。

`data_contract` 回答“字段能不能用”，本模块回答“模型到底用了多少**真自由度**，
以及在压力测试下这类语义缺陷会不会被抓住”。全部纯函数、只依赖 numpy：

- `KNOWN_FDS`：仓库已知的三条函数依赖 / 语义缺陷；
- `make_synthetic_columns(n, seed)`：合成表（含 `priority = 1 + SOFA/10`、
  `los_hours` 实为天数、`isolation` 为 careunit 关键词启发式）；
- `spurious_dof(model_spec, fds)`：统计“冗余字段当独立输入”的次数；
- `field_alignment(model_spec, contracts)`：模型字段被契约覆盖的比例 ∈ [0,1]；
- `refusal_accuracy(reports, ground_truth)`：契约拒答是否预测对了 ∈ [0,1]；
- `ranking_stability(points_a, points_b, k)`：两个排序 top-k 的一致性。

不读数据库、不跑求解器、不访问网络。
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

from domain.optimizer.data_contract import (
    USABLE_LEVELS,
    ConstraintContract,
    FieldContract,
)

# name -> (语义说明, 该字段所依赖的原始字段)
KNOWN_FDS: dict[str, tuple[str, tuple[str, ...]]] = {
    "priority_weight": ("1 + sofa_total / 10", ("sofa_total",)),
    "los_hours": ("outtime - intime in days, mislabeled as hours", ()),
    "isolation": ("careunit keyword heuristic", ("first_careunit",)),
    "isolation_heuristic": ("careunit keyword heuristic", ("first_careunit",)),
}

# 变量/约束里可用来“声明剔除”的键
_EXCLUDE_KEYS = (
    "excluded",
    "excludes",
    "exclude",
    "drop",
    "dropped",
    "derived",
    "decomposed",
    "proxies",
)
_FIELD_KEYS = ("fields", "depends_on", "inputs", "references", "uses")
_NOTE_KEYS = ("redundancy_note", "note", "audit_note")


# --------------------------------------------------------------------------- #
# 输入规范化
# --------------------------------------------------------------------------- #


def _as_fields(values: Any, what: str) -> set[str]:
    if values is None:
        return set()
    if isinstance(values, str):
        return {values.strip()} if values.strip() else set()
    if not isinstance(values, (list, tuple, set, frozenset)):
        raise ValueError(f"{what} 必须是字符串或字符串序列，收到 {type(values).__name__}")
    out: set[str] = set()
    for i, item in enumerate(values):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{what}[{i}] 必须是非空字符串，收到 {item!r}")
        out.add(item.strip())
    return out


def _spec_fields(spec: Any, what: str) -> set[str]:
    """变量/约束 → 它引用的字段集合（字符串即字段名）。"""
    if isinstance(spec, str):
        return _as_fields(spec, what)
    if not isinstance(spec, Mapping):
        raise ValueError(f"{what} 必须是字符串或字典，收到 {type(spec).__name__}")
    fields: set[str] = set()
    for key in _FIELD_KEYS:
        fields |= _as_fields(spec.get(key), f"{what}.{key}")
    return fields


def _spec_audit(spec: Any) -> tuple[set[str], bool]:
    """返回 (被声明剔除/派生的字段, 是否存在任何审计说明)。"""
    if not isinstance(spec, Mapping):
        return set(), False
    dropped: set[str] = set()
    for key in _EXCLUDE_KEYS:
        dropped |= _as_fields(spec.get(key), f"spec.{key}")
    noted = any(
        isinstance(spec.get(key), str) and spec.get(key, "").strip() for key in _NOTE_KEYS
    )
    return dropped, noted


def _normalize_fds(fds: Any) -> dict[str, tuple[str, ...]]:
    """接受 `KNOWN_FDS` 风格（name → (说明, deps)）或 name → deps。"""
    if fds is None:
        return {}
    if not isinstance(fds, Mapping):
        raise ValueError(f"fds 必须是字典，收到 {type(fds).__name__}")
    out: dict[str, tuple[str, ...]] = {}
    for key, value in fds.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"fds 的键必须是非空字符串，收到 {key!r}")
        if isinstance(value, np.ndarray):
            value = value.tolist()
        if isinstance(value, Mapping):
            value = value.get("depends_on") or value.get("fields") or ()
        # KNOWN_FDS 风格：(语义说明, (依赖字段, ...))
        if (
            isinstance(value, (list, tuple))
            and len(value) == 2
            and isinstance(value[0], str)
            and isinstance(value[1], (list, tuple, set, frozenset))
        ):
            value = value[1]
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, (list, tuple, set, frozenset)):
            raise ValueError(f"fds[{key}] 必须是字段序列，收到 {type(value).__name__}")
        deps: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"fds[{key}] 含非法字段 {item!r}")
            deps.append(item.strip())
        out[key.strip()] = tuple(deps)
    return out


def _normalize_model_spec(model_spec: Any) -> tuple[list[Any], list[Any]]:
    if not isinstance(model_spec, Mapping):
        raise ValueError(f"model_spec 必须是字典，收到 {type(model_spec).__name__}")
    if not model_spec:
        raise ValueError("model_spec 为空：至少需要 variables/constraints 之一")
    unknown = set(model_spec) - {"variables", "constraints", "name", "note", "description"}
    if unknown:
        raise ValueError(f"model_spec 含未知键：{sorted(unknown)}")

    def _seq(key: str) -> list[Any]:
        value = model_spec.get(key)
        if value is None:
            return []
        if not isinstance(value, (list, tuple)):
            raise ValueError(f"model_spec['{key}'] 必须是序列，收到 {type(value).__name__}")
        return list(value)

    variables, constraints = _seq("variables"), _seq("constraints")
    if not variables and not constraints:
        raise ValueError("model_spec 为空：variables 与 constraints 都是空的")
    return variables, constraints


def _model_fields(model_spec: Any) -> set[str]:
    variables, constraints = _normalize_model_spec(model_spec)
    fields: set[str] = set()
    for i, var in enumerate(variables):
        fields |= _spec_fields(var, f"variables[{i}]")
    for i, con in enumerate(constraints):
        fields |= _spec_fields(con, f"constraints[{i}]")
    return fields


def _contract_availability(contracts: Any) -> dict[str, str]:
    """字段 → 可用级别；约束契约里出现但未声明级别的字段记为 heuristic。"""
    if contracts is None:
        raise ValueError("contracts 不能为 None")
    if isinstance(contracts, Mapping):
        raise ValueError("contracts 必须是 FieldContract/ConstraintContract 序列")
    if not isinstance(contracts, (list, tuple)):
        raise ValueError(f"contracts 必须是契约序列，收到 {type(contracts).__name__}")

    table: dict[str, str] = {}
    for i, item in enumerate(contracts):
        if isinstance(item, FieldContract):
            table[item.name] = item.availability
        elif isinstance(item, ConstraintContract):
            for name in item.fields:
                table.setdefault(name, "heuristic")
        else:
            raise ValueError(
                f"contracts[{i}] 必须是 FieldContract/ConstraintContract，"
                f"收到 {type(item).__name__}"
            )
    if not table:
        raise ValueError("contracts 为空：无法计算对齐度")
    return table


def _as_1d(values: Any, what: str) -> list[float]:
    """数值序列 → list[float]；非法/空 → ValueError。"""
    if isinstance(values, np.ndarray):
        values = values.tolist()
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{what} 必须是数值序列，收到 {type(values).__name__}")
    if len(values) == 0:
        raise ValueError(f"{what} 为空")
    out: list[float] = []
    for i, v in enumerate(values):
        if isinstance(v, bool):
            raise ValueError(f"{what}[{i}] 是 bool，不是数值")
        try:
            f = float(v)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{what}[{i}] 不是数值：{v!r}") from exc
        if not np.isfinite(f):
            raise ValueError(f"{what}[{i}] 含 NaN/Inf")
        out.append(f)
    return out


def _as_scores(points: Any, what: str) -> list[float]:
    """1-D 分数（越大越好）或 2-D 目标矩阵（按行求和降成标量）→ 分数序列。"""
    if isinstance(points, np.ndarray):
        arr = np.asarray(points, dtype=float)
        if arr.ndim == 1:
            return _as_1d(arr, what)
        if arr.ndim == 2:
            if arr.size == 0:
                raise ValueError(f"{what} 为空")
            if not np.all(np.isfinite(arr)):
                raise ValueError(f"{what} 含 NaN/Inf")
            return [float(v) for v in arr.sum(axis=1)]
        raise ValueError(f"{what} 必须是 1-D 或 2-D 数组，收到 {arr.ndim}-D")

    if not isinstance(points, (list, tuple)):
        raise ValueError(f"{what} 必须是数值序列，收到 {type(points).__name__}")
    if len(points) == 0:
        raise ValueError(f"{what} 为空")
    first = points[0]
    if isinstance(first, (list, tuple, np.ndarray)):
        rows = [_as_1d(row, f"{what}[{i}]") for i, row in enumerate(points)]
        width = len(rows[0])
        if any(len(r) != width for r in rows):
            raise ValueError(f"{what} 的行列不一致")
        return [float(sum(r)) for r in rows]
    return _as_1d(points, what)


# --------------------------------------------------------------------------- #
# 合成数据
# --------------------------------------------------------------------------- #


def make_synthetic_columns(n: int = 200, seed: int = 0) -> dict[str, list]:
    """合成一张带三条已知语义缺陷的表（不做任何 IO）。

    列：`stay_id` / `sofa_total` / `priority_weight` / `los_hours` /
    `first_careunit` / `isolation_heuristic`。其中

    - `priority_weight = 1 + sofa_total / 10`（精确函数依赖，伪自由度来源）；
    - `los_hours` 的数值其实是**天数**（单位错误）；
    - `isolation_heuristic` 由 `first_careunit` 关键词推出（启发式，非原始字段）。
    """
    if isinstance(n, bool) or not isinstance(n, int):
        raise ValueError(f"n 必须是正整数，收到 {n!r}")
    if n < 1:
        raise ValueError(f"n 必须 >= 1，收到 {n}")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError(f"seed 必须是整数，收到 {seed!r}")

    rng = np.random.default_rng(seed)
    sofa = rng.integers(0, 25, size=n)
    days = rng.integers(1, 15, size=n)
    units = rng.choice(["MICU", "SICU", "CCU", "NICU", "TSICU"], size=n)
    iso = [1 if ("MICU" in u or "CCU" in u) else 0 for u in units]

    return {
        "stay_id": list(range(1, n + 1)),
        "sofa_total": [int(x) for x in sofa],
        "priority_weight": [round(1.0 + float(x) / 10.0, 6) for x in sofa],
        "los_hours": [float(d) for d in days],
        "first_careunit": [str(u) for u in units],
        "isolation_heuristic": [int(x) for x in iso],
    }


# --------------------------------------------------------------------------- #
# 三个度量
# --------------------------------------------------------------------------- #


def spurious_dof(model_spec: Any, fds: Any = None) -> int:
    """统计模型里的伪自由度（冗余字段被当独立输入）。

    - 变量同时引用冗余字段与其依赖字段，且没有剔除说明 → 计 1（每个 FD 最多 1）；
    - 约束引用冗余字段当独立输入（未声明 derived/excluded，无审计说明）→ 计 1。

    `fds` 用 `KNOWN_FDS` 风格或 `{name: (deps...)}`；空 FD 图合法（返回 0）。
    """
    variables, constraints = _normalize_model_spec(model_spec)
    graph = _normalize_fds(fds if fds is not None else KNOWN_FDS)

    total = 0
    for name, deps in graph.items():
        for i, var in enumerate(variables):
            fields = _spec_fields(var, f"variables[{i}]")
            if name not in fields:
                continue
            hit = [d for d in deps if d in fields]
            dropped, noted = _spec_audit(var)
            if hit and not noted and name not in dropped and not (set(hit) & dropped):
                total += 1
                break

        for i, con in enumerate(constraints):
            fields = _spec_fields(con, f"constraints[{i}]")
            if name not in fields:
                continue
            dropped, noted = _spec_audit(con)
            # 无依赖字段的缺陷（如 los_hours 单位错误）只要被约束直接引用就算；
            # 有依赖字段时，只有“源字段也在场”（即当独立输入）才算。
            hit = [d for d in deps if d in fields]
            if deps and not hit:
                continue
            if not noted and name not in dropped and not (set(hit) & dropped):
                total += 1
                break
    return int(total)


def field_alignment(model_spec: Any, contracts: Any) -> float:
    """模型引用的字段里，被契约覆盖且可用级别非 blocking 的比例 ∈ [0,1]。"""
    fields = _model_fields(model_spec)
    table = _contract_availability(contracts)
    if not fields:
        return 1.0
    aligned = [f for f in fields if table.get(f) in USABLE_LEVELS]
    return float(len(aligned) / len(fields))


def refusal_accuracy(reports: Any, ground_truth: Any) -> float:
    """契约“该拒答的是否拒答了”的准确率 ∈ [0,1]。"""
    if isinstance(reports, np.ndarray):
        reports = reports.tolist()
    if isinstance(ground_truth, np.ndarray):
        ground_truth = ground_truth.tolist()
    if not isinstance(reports, (list, tuple)):
        raise ValueError(f"reports 必须是序列，收到 {type(reports).__name__}")
    if not isinstance(ground_truth, (list, tuple)):
        raise ValueError(f"ground_truth 必须是序列，收到 {type(ground_truth).__name__}")
    if len(reports) == 0:
        raise ValueError("reports 为空")
    if len(reports) != len(ground_truth):
        raise ValueError(
            f"reports 与 ground_truth 长度不一致：{len(reports)} vs {len(ground_truth)}"
        )

    hits = 0
    for i, (report, truth) in enumerate(zip(reports, ground_truth)):
        if isinstance(report, Mapping):
            action = report.get("action")
        elif isinstance(report, str):
            action = report
        else:
            action = getattr(report, "action", None)
        if action not in ("pass", "degrade", "refuse"):
            raise ValueError(f"reports[{i}] 缺少合法 action，收到 {action!r}")
        hits += int((action == "refuse") == bool(truth))
    return float(hits / len(reports))


def ranking_stability(points_a: Any, points_b: Any, k: int = 3) -> float:
    """两个排序的 top-k 交集比例 ∈ [0,1]（1 = 完全一致）。

    `points_*` 可以是 1-D 分数（越大越好）或 2-D 目标矩阵；矩阵按行求和降成标量。
    """
    if isinstance(k, bool) or not isinstance(k, int):
        raise ValueError(f"k 必须是正整数，收到 {k!r}")
    if k < 1:
        raise ValueError(f"k 必须 >= 1，收到 {k}")
    a = _as_scores(points_a, "points_a")
    b = _as_scores(points_b, "points_b")
    n = min(len(a), len(b))
    if n < 1:
        raise ValueError("points_a/points_b 至少需要 1 个元素")

    def top(values: Sequence[float]) -> set[int]:
        order = sorted(range(len(values)), key=lambda i: (-values[i], i))
        return set(order[: min(k, len(values))])

    denom = min(k, len(a), len(b))
    return float(len(top(a) & top(b)) / denom)


__all__ = [
    "KNOWN_FDS",
    "make_synthetic_columns",
    "spurious_dof",
    "field_alignment",
    "refusal_accuracy",
    "ranking_stability",
]
