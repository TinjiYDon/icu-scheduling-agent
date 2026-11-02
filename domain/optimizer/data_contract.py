"""AIGC 语义可用性契约（DAC）：把“字段能不能当独立输入”写成可校验的契约。

三条实证发现是硬资产，也是本模块的动机：

1. 隔离启发式命中 76,157/94,458（top-20 中 19/20 需 ISO）——`isolation` 不是字段，
   而是从 `careunit` 关键词推出来的**启发式**；
2. `priority ≡ 1 + sofa_total/10`（corr = 1.0、仅 13 个取值）——所谓“优先级模型”
   只是 SOFA 的线性重编码，两者同时当自变量是**伪自由度**；
3. `los_hours` 实为“天”——单位错误，直接当小时用会把 LOS 窗口放大 24×。

AIGC 生成优化模型时，这些“语义可用性”必须**先声明、后可校验**。本模块只做
契约判定，不做 IO、不读数据库、不调求解器：

- `FieldContract` / `ConstraintContract`：字段与约束的可用性声明；
- `check_contract(contracts, columns, fd_map)` → `ContractReport`（纯函数，无 IO）；
- `degrade_or_refuse(report, policy)` → `{"action", "reason"}` 三档策略；
- `contract_from_dicts(items)`：从 YAML/JSON 里读到的字典构造约束契约。

分级：`exact` / `proxy` / `heuristic` 可用（启发式需标注），
`stale` / `unit_error` / `missing` 视为违规——前两者降级，`missing` 直接拒绝。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

AVAILABILITY_LEVELS = ("exact", "proxy", "heuristic", "stale", "unit_error", "missing")

# 可用但必须标注的级别
USABLE_LEVELS = frozenset({"exact", "proxy", "heuristic"})
# 违规级别：stale/unit_error → degrade；missing → refuse
BLOCKING_LEVELS = frozenset({"stale", "unit_error", "missing"})

ACTIONS = ("pass", "degrade", "refuse")
POLICIES = ("strict", "advisory", "lenient")


def _as_name(value: Any, what: str) -> str:
    """非空字符串校验（去掉首尾空白）。"""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{what} 必须是非空字符串，收到 {value!r}")
    return value.strip()


def _as_names(values: Any, what: str) -> tuple[str, ...]:
    """字符串序列校验 → 去重后保持输入顺序的 tuple。"""
    if values is None:
        return ()
    if isinstance(values, str):
        raise ValueError(f"{what} 必须是字符串序列，而不是单个字符串 {values!r}")
    if not isinstance(values, (list, tuple, set, frozenset)):
        raise ValueError(f"{what} 必须是字符串序列，收到 {type(values).__name__}")
    out: list[str] = []
    for i, item in enumerate(values):
        name = _as_name(item, f"{what}[{i}]")
        if name not in out:
            out.append(name)
    return tuple(out)


@dataclass(frozen=True)
class FieldContract:
    """单字段的可用性声明。

    `availability` 必须 ∈ `AVAILABILITY_LEVELS`；`depends_on` 声明该字段由哪些
    原始字段决定（如 `priority_weight` ← `sofa_total`）；`redundant_with` 声明
    哪些字段**与该字段冗余**（即同列出现时即可丢弃）。
    """

    name: str
    availability: str
    depends_on: tuple[str, ...] = ()
    redundant_with: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        name = _as_name(self.name, "FieldContract.name")
        if self.availability not in AVAILABILITY_LEVELS:
            raise ValueError(
                f"FieldContract({name}).availability={self.availability!r} 不在 "
                f"{AVAILABILITY_LEVELS} 内"
            )
        object.__setattr__(self, "name", name)
        object.__setattr__(
            self, "depends_on", _as_names(self.depends_on, f"FieldContract({name}).depends_on")
        )
        object.__setattr__(
            self,
            "redundant_with",
            _as_names(self.redundant_with, f"FieldContract({name}).redundant_with"),
        )

    @property
    def usable(self) -> bool:
        return self.availability in USABLE_LEVELS

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "availability": self.availability,
            "depends_on": list(self.depends_on),
            "redundant_with": list(self.redundant_with),
        }


@dataclass(frozen=True)
class ConstraintContract:
    """单约束的字段依赖声明：任一字段缺失即 `refuse`。"""

    name: str
    fields: tuple[str, ...]
    failure_mode: str = ""

    def __post_init__(self) -> None:
        name = _as_name(self.name, "ConstraintContract.name")
        fields = _as_names(self.fields, f"ConstraintContract({name}).fields")
        if not fields:
            raise ValueError(f"ConstraintContract({name}).fields 不能为空")
        if not isinstance(self.failure_mode, str):
            raise ValueError(f"ConstraintContract({name}).failure_mode 必须是字符串")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "fields", fields)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "fields": list(self.fields),
            "failure_mode": self.failure_mode,
        }


@dataclass(frozen=True)
class ContractReport:
    """契约判定结果：`ok` 等价于“无违规”，`action` 是严重性分档。"""

    ok: bool
    violations: tuple[str, ...]
    action: str

    def __post_init__(self) -> None:
        if self.action not in ACTIONS:
            raise ValueError(f"ContractReport.action={self.action!r} 不在 {ACTIONS} 内")
        violations = _as_names(self.violations, "ContractReport.violations")
        if not isinstance(self.ok, bool):
            raise ValueError("ContractReport.ok 必须是 bool")
        if violations and self.ok:
            raise ValueError("ContractReport.ok=True 但存在 violations")
        object.__setattr__(self, "violations", violations)

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "violations": list(self.violations),
            "action": self.action,
        }


def contract_from_dicts(items: Any) -> tuple[ConstraintContract, ...]:
    """`[{"name": ..., "fields": [...], "failure_mode": ...}, ...]` → 约束契约元组。"""
    if not isinstance(items, (list, tuple)):
        raise ValueError(f"items 必须是字典序列，收到 {type(items).__name__}")
    out: list[ConstraintContract] = []
    for i, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise ValueError(f"items[{i}] 必须是字典，收到 {type(item).__name__}")
        unknown = set(item) - {"name", "fields", "failure_mode"}
        if unknown:
            raise ValueError(f"items[{i}] 含未知键：{sorted(unknown)}")
        if "name" not in item or "fields" not in item:
            raise ValueError(f"items[{i}] 缺 name/fields")
        out.append(
            ConstraintContract(
                name=item["name"],
                fields=item["fields"],
                failure_mode=str(item.get("failure_mode", "") or ""),
            )
        )
    if not out:
        raise ValueError("items 为空：至少需要 1 条约束契约")
    return tuple(out)


def _normalize_columns(columns: Any) -> frozenset[str]:
    """列名集合：接受字符串序列或 `{name: series}` 映射（取键）。"""
    if columns is None:
        raise ValueError("columns 不能为 None")
    if isinstance(columns, Mapping):
        names = list(columns.keys())
    elif isinstance(columns, (str, bytes)):
        raise ValueError("columns 必须是字符串序列，而不是单个字符串")
    else:
        try:
            names = list(columns)
        except TypeError as exc:
            raise ValueError(f"columns 必须是可迭代的列名，收到 {type(columns).__name__}") from exc
    if not names:
        raise ValueError("columns 为空：至少需要 1 列")
    return frozenset(_as_name(n, f"columns[{i}]") for i, n in enumerate(names))


def _normalize_fd_map(fd_map: Any) -> dict[str, tuple[str, ...]]:
    """函数依赖图校验：`{determined_field: (determinant, ...)}`，允许空图。"""
    if fd_map is None:
        return {}
    if not isinstance(fd_map, Mapping):
        raise ValueError(f"fd_map 必须是字典，收到 {type(fd_map).__name__}")
    out: dict[str, tuple[str, ...]] = {}
    for key, value in fd_map.items():
        name = _as_name(key, "fd_map 的键")
        out[name] = _as_names(value, f"fd_map[{name}]")
    return out


def _split_contracts(
    contracts: Any,
) -> tuple[tuple[FieldContract, ...], tuple[ConstraintContract, ...]]:
    """契约序列 → (字段契约, 约束契约)；也接受 `{"fields": [...], "constraints": [...]}`。"""
    if isinstance(contracts, Mapping):
        unknown = set(contracts) - {"fields", "constraints"}
        if unknown:
            raise ValueError(f"contracts 含未知键：{sorted(unknown)}")
        raw: list[Any] = []
        raw.extend(contracts.get("fields") or ())
        raw.extend(contracts.get("constraints") or ())
    elif isinstance(contracts, (list, tuple)):
        raw = list(contracts)
    else:
        raise ValueError(
            f"contracts 必须是契约序列或字典，收到 {type(contracts).__name__}"
        )
    if not raw:
        raise ValueError("contracts 为空：至少需要 1 条契约")

    fields: list[FieldContract] = []
    constraints: list[ConstraintContract] = []
    for i, item in enumerate(raw):
        if isinstance(item, FieldContract):
            fields.append(item)
        elif isinstance(item, ConstraintContract):
            constraints.append(item)
        elif isinstance(item, Mapping):
            raise ValueError(
                f"contracts[{i}] 是裸字典；字段请用 FieldContract，"
                f"约束请用 contract_from_dicts() 转换"
            )
        else:
            raise ValueError(
                f"contracts[{i}] 必须是 FieldContract/ConstraintContract，"
                f"收到 {type(item).__name__}"
            )
    return tuple(fields), tuple(constraints)


def check_contract(
    contracts: Any,
    columns: Any,
    fd_map: Any = None,
) -> ContractReport:
    """纯函数契约校验（无 IO）：返回 `ContractReport`。

    规则（严重性从低到高）：

    - 违规但不致命（→ `degrade`）：字段可用级别 ∈ {stale, unit_error}；
      冗余字段与其源字段/VoI 依赖同时出现在列里（未剔除）；
    - 致命（→ `refuse`）：某字段可用级别为 `missing`，或某约束的任一字段不在列里；
    - 无违规 → `pass`。
    """
    cols = _normalize_columns(columns)
    fds = _normalize_fd_map(fd_map)
    field_contracts, constraint_contracts = _split_contracts(contracts)

    violations: list[str] = []
    fatal = False

    for fc in field_contracts:
        if fc.name not in cols:
            continue  # 列里没有该字段：由引用它的约束负责报 refuse

        if fc.availability in BLOCKING_LEVELS:
            violations.append(
                f"字段 '{fc.name}' 可用级别为 {fc.availability}，不可作为独立输入"
            )
            if fc.availability == "missing":
                fatal = True

        for other in fc.redundant_with:
            if other in cols:
                violations.append(
                    f"字段 '{other}' 与 '{fc.name}' 冗余，但同时作为独立输入"
                )

        for determinant in fds.get(fc.name, ()):
            # depends_on 里已声明的依赖算“已审计”，不重复计违规；
            # 未声明的隐式依赖才是伪自由度。
            if determinant in cols and determinant not in fc.depends_on:
                violations.append(
                    f"字段 '{fc.name}' 由 '{determinant}' 函数依赖决定，但同时作为独立输入"
                )

    # fd_map 里声明、但没有对应 FieldContract 的冗余也照样算
    documented = {fc.name: set(fc.depends_on) for fc in field_contracts}
    for name, determinants in fds.items():
        if name not in cols:
            continue
        hit = [
            d for d in determinants if d in cols and d not in documented.get(name, set())
        ]
        if hit:
            violations.append(
                f"字段 '{name}' 与 {hit} 构成函数依赖（fd_map），但同时作为独立输入"
            )

    for cc in constraint_contracts:
        missing = [f for f in cc.fields if f not in cols]
        if missing:
            fatal = True
            detail = f"（失败模式：{cc.failure_mode}）" if cc.failure_mode.strip() else ""
            violations.append(f"约束 '{cc.name}' 缺字段 {missing}{detail}")

    # 去重但保持首次出现的顺序
    seen: set[str] = set()
    unique: list[str] = []
    for item in violations:
        if item not in seen:
            seen.add(item)
            unique.append(item)

    if fatal:
        action = "refuse"
    elif unique:
        action = "degrade"
    else:
        action = "pass"

    return ContractReport(ok=not unique, violations=tuple(unique), action=action)


def degrade_or_refuse(report: ContractReport, policy: str = "strict") -> dict:
    """把 `ContractReport` 映射成执行动作。

    - `strict`：任何违规 → `refuse`（默认，AIGC 生成前的最保守档）；
    - `advisory`：沿用报告自身的 `action`（`degrade` 仍可跑，但要标注）；
    - `lenient`：违规最多 `degrade`，只有“无违规”才 `pass`。
    """
    if not isinstance(report, ContractReport):
        raise ValueError(f"report 必须是 ContractReport，收到 {type(report).__name__}")
    if policy not in POLICIES:
        raise ValueError(f"policy={policy!r} 不在 {POLICIES} 内")

    if not report.violations:
        return {"action": "pass", "reason": "contract satisfied"}

    n = len(report.violations)
    detail = "; ".join(report.violations[:3])
    if n > 3:
        detail += f"; (+{n - 3} more)"

    if policy == "strict":
        return {
            "action": "refuse",
            "reason": f"strict policy: {n} contract violation(s): {detail}",
        }
    if policy == "lenient":
        return {
            "action": "degrade",
            "reason": f"lenient policy: {n} contract violation(s) tolerated with flags: {detail}",
        }
    return {"action": report.action, "reason": f"advisory policy: {detail}"}


__all__ = [
    "AVAILABILITY_LEVELS",
    "USABLE_LEVELS",
    "BLOCKING_LEVELS",
    "ACTIONS",
    "POLICIES",
    "FieldContract",
    "ConstraintContract",
    "ContractReport",
    "check_contract",
    "degrade_or_refuse",
    "contract_from_dicts",
]
