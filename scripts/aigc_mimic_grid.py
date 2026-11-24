"""MIMIC 网格运行器：6 场景 × N seed 的 ε 网格 + HV + 同池反事实（B_pool）。

设计口径
--------
1. **求解链不重写**：直接复用 ``domain.optimizer.moo_phase3``
   （``run_payoff_table`` → ``run_epsilon_grid_scan`` → ``hypervolume``，
   与 ``application/run_moo_phase3.py`` 同一条链），只把 ``solve`` 回调换成
   “固定候选池 + 场景资源覆盖”的 ``run_assignment`` 调用。
2. **两种取池方式**（``--source``）：
   - ``db``（默认）：与 ``application/run_moo_phase4.py`` 同口径，从
     ``staging.icustays`` + ``feat.patient_priority`` + ``feat.sofa_timeseries`` 取池；
   - ``synthetic``：仓内合成池，**不读 MIMIC、不连数据库**，仅供 ``--smoke`` 自检。
3. **确定性**：``num_search_workers=1`` + 固定 ``random_seed``（按 seed）。
4. **F1 门**：DUA/CITI 未确认时只允许候选数 ≤100；全量网格必须显式
   ``AIGC_MIMIC_ALLOW=1``。``--smoke`` 不受此限。

输出（``--out``）: ``{config, runs: [...], scenarios: {...}, pool_effect: {...}}``。

用法
----
    python scripts/aigc_mimic_grid.py --smoke                  # 自检：1 场景 / 1 seed / 30 候选
    python scripts/aigc_mimic_grid.py --levels 2 --seeds 1      # 小网格（需 AIGC_MIMIC_ALLOW=1）
    python scripts/aigc_mimic_grid.py --source synthetic        # 合成池干跑（不读 MIMIC）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # 允许 `python scripts/aigc_mimic_grid.py` 直接跑
    sys.path.insert(0, str(ROOT))

from domain.optimizer.objective_semantics import HIGH_RISK_SOFA  # noqa: E402
from domain.optimizer.pool_effect import pool_effect, summarize_pool_effect  # noqa: E402

OUT_DIR = ROOT / "reports" / "aigc"
DEFAULT_OUT = OUT_DIR / "mimic_grid.json"
SMOKE_OUT = OUT_DIR / "mimic_grid_smoke.json"

F1_GATE = "F1-GATE: 需要 DUA/CITI 已确认"
ALLOW_ENV = "AIGC_MIMIC_ALLOW"
CANDIDATE_HARD_CAP = 100
SMOKE_POOL_CAP = 30
SMOKE_MAX_TIME = 2.0
HIGH_SOFA_BUMP = 1.5  # high_acuity 场景：SOFA≥10 的 priority_weight 放大倍数

ISOLATION_CAREUNITS = ("MICU", "SICU", "CVICU", "NSICU")
PLAIN_CAREUNITS = ("CCU", "NICU", "TSICU", "UNK")


# --------------------------------------------------------------------------- #
# 1. 场景定义（resource_overrides 级别）
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class GridScenario:
    """一个网格场景：资源覆盖 + 候选池上限 + （可选）优先级改写规则。"""

    id: str
    name: str
    description: str
    resource_overrides: Mapping[str, Any] = field(default_factory=dict)
    pool_cap: int | None = None  # None → 用 --max-patients
    priority_rule: str | None = None  # None | "high_sofa"
    expectation: str = "effect"  # effect | neutral_control


SCENARIOS: tuple[GridScenario, ...] = (
    GridScenario(
        id="baseline",
        name="基线",
        description="默认资源（20 床 / 4 隔离 / 8 呼吸机），全池",
    ),
    GridScenario(
        id="more_beds",
        name="扩容",
        description="n_beds=24（分区按比例缩放）",
        resource_overrides={"n_beds": 24},
    ),
    GridScenario(
        id="fewer_vents",
        name="呼吸机不足",
        description="n_ventilators=4",
        resource_overrides={"n_ventilators": 4},
    ),
    GridScenario(
        id="more_iso",
        name="隔离床扩容",
        description="n_isolation_beds=8",
        resource_overrides={"n_isolation_beds": 8},
    ),
    GridScenario(
        id="small_pool",
        name="候选池截断",
        description="候选截断 50（pool 变小，机制不变）",
        pool_cap=50,
    ),
    GridScenario(
        id="high_acuity",
        name="高 SOFA 加权",
        description=f"负对照：SOFA≥{HIGH_RISK_SOFA} 权重 ×{HIGH_SOFA_BUMP}（归一化+同池下预期无效应）",
        priority_rule="high_sofa",
        expectation="neutral_control",
    ),
)

BASELINE_ID = "baseline"


def scenario_map() -> dict[str, GridScenario]:
    return {s.id: s for s in SCENARIOS}


def get_scenarios(ids: Sequence[str] | None = None) -> list[GridScenario]:
    """按 id 取场景；``ids=None`` 返回全部 6 个。未知 id → ValueError。"""
    by_id = scenario_map()
    if ids is None:
        return list(SCENARIOS)
    wanted = [str(x).strip() for x in ids if str(x).strip()]
    if not wanted:
        raise ValueError("scenarios 为空：至少需要 1 个场景")
    unknown = [x for x in wanted if x not in by_id]
    if unknown:
        raise ValueError(f"unknown scenario id(s): {', '.join(unknown)}")
    seen: list[GridScenario] = []
    for sid in wanted:
        spec = by_id[sid]
        if spec not in seen:
            seen.append(spec)
    return seen


def effective_pool_cap(scenario: GridScenario, max_patients: int) -> int:
    """场景池上限：场景自带 cap 优先，否则用 --max-patients。"""
    cap = int(scenario.pool_cap if scenario.pool_cap is not None else max_patients)
    if cap <= 0:
        raise ValueError(f"pool cap 必须为正，收到 {cap}")
    return cap


def validate_grid_args(
    *,
    levels: int,
    seeds: int,
    max_time: float,
    max_patients: int,
    scenarios: Sequence[GridScenario],
) -> None:
    """参数自检；任何非法输入直接 ValueError（不做静默兜底）。"""
    if int(levels) < 2:
        raise ValueError("levels 必须 ≥ 2（ε 网格至少 2 个水平）")
    if int(seeds) < 1:
        raise ValueError("seeds 必须 ≥ 1")
    if not np.isfinite(float(max_time)) or float(max_time) <= 0:
        raise ValueError("max_time 必须是有限正数")
    if int(max_patients) < 1:
        raise ValueError("max_patients 必须 ≥ 1")
    if not scenarios:
        raise ValueError("scenarios 为空：至少需要 1 个场景")
    ids = [s.id for s in scenarios]
    if len(set(ids)) != len(ids):
        raise ValueError("scenarios 有重复 id")


def enforce_mimic_gate(
    *,
    source: str,
    candidate_cap: int,
    smoke: bool,
    env: Mapping[str, str],
) -> str:
    """F1 门：MIMIC 候选数 >100 时必须显式 ``AIGC_MIMIC_ALLOW=1``。

    返回放行原因字符串；不放行时 ValueError（调用方以非零码退出）。
    """
    if smoke:
        return "smoke"
    if source != "db":
        return "synthetic"
    if int(candidate_cap) > CANDIDATE_HARD_CAP:
        if str(env.get(ALLOW_ENV, "")).strip() != "1":
            raise ValueError(
                f"{F1_GATE}；候选数 {candidate_cap} > {CANDIDATE_HARD_CAP} 需要 "
                f"{ALLOW_ENV}=1 才允许跑（防止误跑全量网格）"
            )
        return f"{ALLOW_ENV}=1"
    return f"candidates<={CANDIDATE_HARD_CAP}"


# --------------------------------------------------------------------------- #
# 2. 候选池：db / synthetic
# --------------------------------------------------------------------------- #

POOL_SQL = """
SELECT s.stay_id,
       COALESCE(p.priority_weight, 1.0) AS priority_weight,
       COALESCE(so.sofa_total, 0) AS sofa_total,
       s.first_careunit
FROM staging.icustays s
LEFT JOIN feat.patient_priority p ON s.stay_id = p.stay_id
LEFT JOIN feat.sofa_timeseries so ON s.stay_id = so.stay_id AND so.hour_index = 0
ORDER BY priority_weight DESC, sofa_total DESC, s.stay_id
LIMIT :cap
"""


def _normalize_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out = [
        {
            "stay_id": int(r["stay_id"]),
            "priority_weight": float(r["priority_weight"] or 1.0),
            "sofa_total": float(r["sofa_total"] or 0.0),
            "first_careunit": r.get("first_careunit"),
        }
        for r in rows
    ]
    out.sort(
        key=lambda s: (-s["priority_weight"], -s["sofa_total"], s["stay_id"])
    )
    return out


def fetch_pool_db(cap: int) -> list[dict[str, Any]]:
    """与 run_moo_phase4 / run_assignment 同口径读候选池（需要数据库）。"""
    from sqlalchemy import text

    from infra.db import get_engine

    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(POOL_SQL), {"cap": int(cap)}).mappings().all()
    pool = _normalize_rows(rows)
    if not pool:
        raise RuntimeError("候选池为空：检查 staging/feat 是否已 ETL（见 docs/DATA_LOCAL.md）")
    return pool


def synthetic_pool(cap: int, *, seed: int = 0) -> list[dict[str, Any]]:
    """合成候选池（不读 MIMIC）：SOFA 整数分布 + 隔离/非隔离 careunit 混合。

    优先级沿用仓内已实证的关系 ``priority = 1 + sofa_total / 10``（见
    docs/AIGC_CONTRACT.md 第 1 节），因此合成池只用于**口径自检**，
    不是临床证据。
    """
    cap = int(cap)
    if cap <= 0:
        raise ValueError("cap 必须 ≥ 1")
    rng = np.random.default_rng(int(seed))
    sofas = rng.integers(0, 21, size=cap)
    iso_mask = rng.random(cap) < 0.4
    rows = []
    for i in range(cap):
        sofa = int(sofas[i])
        pool_cu = ISOLATION_CAREUNITS if iso_mask[i] else PLAIN_CAREUNITS
        rows.append(
            {
                "stay_id": 10_000_000 + i,
                "priority_weight": 1.0 + sofa / 10.0,
                "sofa_total": float(sofa),
                "first_careunit": pool_cu[int(rng.integers(0, len(pool_cu)))],
            }
        )
    return _normalize_rows(rows)


def fetch_pool(source: str, cap: int, *, seed: int = 0) -> list[dict[str, Any]]:
    if source == "db":
        return fetch_pool_db(cap)
    if source == "synthetic":
        return synthetic_pool(cap, seed=seed)
    raise ValueError(f"unknown source: {source}")


def priority_overrides_for(
    rows: Sequence[Mapping[str, Any]], rule: str | None
) -> dict[int, float] | None:
    """场景级 priority 改写（等价于 ``run_assignment(priority_overrides=...)``）。"""
    if rule is None:
        return None
    if rule != "high_sofa":
        raise ValueError(f"unknown priority_rule: {rule}")
    overrides = {
        int(r["stay_id"]): float(r["priority_weight"]) * HIGH_SOFA_BUMP
        for r in rows
        if float(r["sofa_total"]) >= HIGH_RISK_SOFA
    }
    return overrides or None


# --------------------------------------------------------------------------- #
# 3. 求解注入：合成池 + 单 worker 确定性
# --------------------------------------------------------------------------- #


class _FakeResult:
    def __init__(self, rows: Sequence[Mapping[str, Any]]) -> None:
        self._rows = list(rows)

    def mappings(self) -> "_FakeResult":
        return self

    def all(self) -> list[Mapping[str, Any]]:
        return list(self._rows)


class _FakeConn:
    def __init__(self, rows: Sequence[Mapping[str, Any]]) -> None:
        self._rows = rows

    def __enter__(self) -> "_FakeConn":
        return self

    def __exit__(self, *args: object) -> bool:
        return False

    def execute(self, *args: object, **kwargs: object) -> _FakeResult:
        return _FakeResult(self._rows)


class _FakeEngine:
    def __init__(self, rows: Sequence[Mapping[str, Any]]) -> None:
        self._rows = rows

    def connect(self) -> _FakeConn:
        return _FakeConn(self._rows)


@contextmanager
def memory_pool(rows: Sequence[Mapping[str, Any]]) -> Iterator[None]:
    """把合成候选池注入**生产求解链**（只替换 ``get_engine``，不改 SQL 语义）。

    这样 ``--smoke`` 跑的是真正的 ``run_assignment`` 与 ε/HV 链路，
    只是数据来自内存而不是 MIMIC —— 自检覆盖的是代码，不是数据。
    """
    from domain.optimizer import cp_sat

    original = cp_sat.get_engine
    cp_sat.get_engine = lambda: _FakeEngine(rows)  # type: ignore[assignment]
    try:
        yield
    finally:
        cp_sat.get_engine = original  # type: ignore[assignment]


@contextmanager
def deterministic_solver(seed: int, *, enabled: bool = True) -> Iterator[bool]:
    """``num_search_workers=1`` + 固定 ``random_seed``（run_assignment 不暴露该参数）。"""
    from domain.optimizer import multiobjective

    original = getattr(multiobjective, "_new_solver", None)
    if not enabled or original is None:
        yield False
        return

    def _patched(max_time_seconds: float) -> Any:
        solver = original(max_time_seconds)
        solver.parameters.num_search_workers = 1
        solver.parameters.random_seed = int(seed)
        return solver

    multiobjective._new_solver = _patched
    try:
        yield True
    finally:
        multiobjective._new_solver = original


# --------------------------------------------------------------------------- #
# 4. 纯函数：单次记录统计 / 场景汇总 / B_pool
# --------------------------------------------------------------------------- #


def mean_std(values: Sequence[float]) -> tuple[float, float]:
    """均值与总体标准差（ddof=0）；空输入 → ValueError。"""
    arr = np.asarray(list(values), dtype=float)
    if arr.size == 0:
        raise ValueError("mean_std 需要至少 1 个数")
    if arr.ndim != 1 or not np.all(np.isfinite(arr)):
        raise ValueError("mean_std 只接受有限的一维数值")
    return float(arr.mean()), float(arr.std(ddof=0))


def front_stats(scan: Mapping[str, Any]) -> dict[str, float]:
    """非支配前沿上的 ``assigned`` / ``high_risk`` 均值（前沿为空 → 0）。"""
    front = list(scan.get("front") or [])
    if not front:
        return {"assigned": 0.0, "high_risk": 0.0}
    assigned = [float((p.get("values") or {}).get("occupancy", 0)) for p in front]
    high_risk = [float((p.get("values") or {}).get("high_risk", 0)) for p in front]
    return {
        "assigned": float(np.mean(assigned)),
        "high_risk": float(np.mean(high_risk)),
    }


def solve_time_sum(payoff: Mapping[str, Any], scan: Mapping[str, Any]) -> float:
    rows = sum(float(r.get("wall_time_seconds") or 0.0) for r in payoff.get("rows") or [])
    points = sum(
        float(p.get("wall_time_seconds") or 0.0) for p in scan.get("points") or []
    )
    return float(rows + points)


def build_run_record(
    *,
    scenario: str,
    seed: int,
    payoff: Mapping[str, Any],
    scan: Mapping[str, Any],
    pool_size: int,
    pool_cap: int,
) -> dict[str, Any]:
    stats = front_stats(scan)
    return {
        "scenario": str(scenario),
        "seed": int(seed),
        "n_feasible": int(scan.get("n_feasible") or 0),
        "n_front": int(scan.get("n_nondominated") or 0),
        "hv": float(scan.get("hypervolume") or 0.0),
        "assigned": stats["assigned"],
        "high_risk": stats["high_risk"],
        "solve_time_sum": solve_time_sum(payoff, scan),
        "n_grid": int(scan.get("n_grid") or 0),
        "pool_size": int(pool_size),
        "pool_cap": int(pool_cap),
    }


def aggregate_runs(runs: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """按场景汇总：``hv`` 均值±std、``high_risk`` / ``assigned`` 均值等。"""
    if not runs:
        raise ValueError("runs 为空：至少需要 1 条记录")
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for run in runs:
        grouped.setdefault(str(run["scenario"]), []).append(run)

    out: dict[str, dict[str, Any]] = {}
    for sid, items in grouped.items():
        hv_mean, hv_std = mean_std([float(i["hv"]) for i in items])
        high_risk_mean, high_risk_std = mean_std([float(i["high_risk"]) for i in items])
        assigned_mean, _ = mean_std([float(i["assigned"]) for i in items])
        feasible_mean, _ = mean_std([float(i["n_feasible"]) for i in items])
        front_mean, _ = mean_std([float(i["n_front"]) for i in items])
        time_mean, _ = mean_std([float(i["solve_time_sum"]) for i in items])
        out[sid] = {
            "n_seeds": len(items),
            "seeds": sorted(int(i["seed"]) for i in items),
            "hv_mean": hv_mean,
            "hv_std": hv_std,
            "high_risk_mean": high_risk_mean,
            "high_risk_std": high_risk_std,
            "assigned_mean": assigned_mean,
            "n_feasible_mean": feasible_mean,
            "n_front_mean": front_mean,
            "solve_time_sum_mean": time_mean,
            "pool_cap": int(items[0]["pool_cap"]),
        }
    return out


def pool_effect_rows(
    aggregates: Mapping[str, Mapping[str, Any]],
    matched_baseline: Mapping[str, Mapping[str, Any]] | None = None,
    *,
    baseline_id: str = BASELINE_ID,
) -> dict[str, Any]:
    """B_pool 表：baseline 与每个场景的同池反事实。

    - ``naive_*``：各场景跑在**自己的池**上（整池口径）；
    - ``matched_*``：baseline 重跑在**该场景的池**上（同池口径）；
    - ``pool_effect = delta_naive − delta_match``。

    因此 ``small_pool``（只换池）的差值全部落进 ``pool_effect``，
    而 `more_beds` / `fewer_vents` / ... （同池只换机制）的 ``pool_effect`` 为 0。
    """
    if baseline_id not in aggregates:
        raise ValueError(f"aggregates 缺 baseline 场景 {baseline_id!r}")
    base = aggregates[baseline_id]
    matched = matched_baseline or {}

    rows: list[dict[str, Any]] = []
    hv_effects: dict[str, float] = {}
    for sid, agg in aggregates.items():
        if sid == baseline_id:
            continue
        same_pool = matched.get(sid) or {}
        hv_eff = pool_effect(
            naive_a=float(base["hv_mean"]),
            naive_b=float(agg["hv_mean"]),
            matched_a=float(same_pool.get("hv_mean", base["hv_mean"])),
            matched_b=float(agg["hv_mean"]),
        )
        high_risk_eff = pool_effect(
            naive_a=float(base["high_risk_mean"]),
            naive_b=float(agg["high_risk_mean"]),
            matched_a=float(same_pool.get("high_risk_mean", base["high_risk_mean"])),
            matched_b=float(agg["high_risk_mean"]),
        )
        hv_effects[sid] = float(hv_eff["pool_effect"])
        rows.append(
            {
                "scenario": sid,
                "matched_pool_cap": same_pool.get("pool_cap", agg.get("pool_cap")),
                "metrics": {"hv": hv_eff, "high_risk": high_risk_eff},
                "B_pool_hv": float(hv_eff["pool_effect"]),
            }
        )

    summary = (
        summarize_pool_effect(hv_effects)
        if hv_effects
        else {"n_metrics": 0, "note": "只有 baseline 场景，无对照"}
    )
    return {
        "baseline": baseline_id,
        "baseline_hv_mean": float(base["hv_mean"]),
        "rows": rows,
        "summary": summary,
    }


# --------------------------------------------------------------------------- #
# 5. 网格编排
# --------------------------------------------------------------------------- #


def _solve_for(
    rows: Sequence[Mapping[str, Any]],
    *,
    source: str,
    scenario: GridScenario,
    priority_overrides: Mapping[int, float] | None,
    max_time: float,
) -> Any:
    from functools import partial

    from domain.optimizer.cp_sat import run_assignment

    stay_ids = None
    if source == "db":
        stay_ids = [int(r["stay_id"]) for r in rows]
    return partial(
        run_assignment,
        persist=False,
        stay_ids=stay_ids,
        resource_overrides=dict(scenario.resource_overrides) or None,
        priority_overrides=priority_overrides,
        max_time_seconds=float(max_time),
    )


def run_scenario_seeds(
    scenario: GridScenario,
    *,
    seeds: Sequence[int],
    levels: int,
    max_time: float,
    max_patients: int,
    source: str,
    max_points: int | None = None,
    deterministic: bool = True,
    progress: Any = None,
) -> list[dict[str, Any]]:
    """跑 1 个场景 × N seed 的 ε 网格，返回 run 记录。"""
    from domain.optimizer.moo_phase3 import (
        DEFAULT_GRID_OBJECTIVES,
        DEFAULT_OBJECTIVES,
        DEFAULT_PRIMARY,
        run_epsilon_grid_scan,
        run_payoff_table,
    )

    cap = effective_pool_cap(scenario, max_patients)
    records: list[dict[str, Any]] = []

    for seed in seeds:
        rows = fetch_pool(source, cap, seed=seed)
        overrides = priority_overrides_for(rows, scenario.priority_rule)
        solve = _solve_for(
            rows,
            source=source,
            scenario=scenario,
            priority_overrides=overrides,
            max_time=max_time,
        )
        ctx = memory_pool(rows) if source == "synthetic" else _null_context()
        with ctx, deterministic_solver(seed, enabled=deterministic):
            payoff = run_payoff_table(
                solve, objectives=DEFAULT_OBJECTIVES, split=None, persist=False
            )
            scan = run_epsilon_grid_scan(
                solve,
                payoff=payoff,
                primary=DEFAULT_PRIMARY,
                grid_objectives=DEFAULT_GRID_OBJECTIVES,
                levels=int(levels),
                split=None,
                persist=False,
                max_points=max_points,
                progress=progress,
            )
        record = build_run_record(
            scenario=scenario.id,
            seed=seed,
            payoff=payoff,
            scan=scan,
            pool_size=len(rows),
            pool_cap=cap,
        )
        records.append(record)
        print(
            json.dumps(
                {
                    "scenario": scenario.id,
                    "seed": int(seed),
                    "hv": round(record["hv"], 6),
                    "n_front": record["n_front"],
                    "n_feasible": record["n_feasible"],
                    "pool": record["pool_size"],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    return records


@contextmanager
def _null_context() -> Iterator[None]:
    yield


def run_grid(
    *,
    scenarios: Sequence[GridScenario],
    seeds: Sequence[int],
    levels: int,
    max_time: float,
    max_patients: int,
    source: str,
    max_points: int | None = None,
    deterministic: bool = True,
    progress: Any = None,
) -> dict[str, Any]:
    """6 场景 × N seed 全网格 + 场景汇总 + B_pool。"""
    all_runs: list[dict[str, Any]] = []
    for scenario in scenarios:
        print(f"[scenario] {scenario.id} cap={effective_pool_cap(scenario, max_patients)}", flush=True)
        records = run_scenario_seeds(
            scenario,
            seeds=seeds,
            levels=levels,
            max_time=max_time,
            max_patients=max_patients,
            source=source,
            max_points=max_points,
            deterministic=deterministic,
            progress=progress,
        )
        all_runs.extend(records)

    aggregates = aggregate_runs(all_runs)

    # 同池口径：baseline 重跑在**每个场景的池**上（只对池不同的场景产生非零 B_pool）
    matched: dict[str, dict[str, Any]] = {}
    if BASELINE_ID in {s.id for s in scenarios}:
        baseline_spec = scenario_map()[BASELINE_ID]
        cache: dict[int, dict[str, Any]] = {}
        base_cap = effective_pool_cap(baseline_spec, max_patients)
        if BASELINE_ID in aggregates:  # 复用主网格结果，避免重复求解
            cache[base_cap] = dict(aggregates[BASELINE_ID], pool_cap=base_cap)
        for scenario in scenarios:
            cap = effective_pool_cap(scenario, max_patients)
            if cap not in cache:
                records = run_scenario_seeds(
                    baseline_spec,
                    seeds=seeds,
                    levels=levels,
                    max_time=max_time,
                    max_patients=cap,
                    source=source,
                    max_points=max_points,
                    deterministic=deterministic,
                    progress=None,
                )
                agg = aggregate_runs(records)
                agg["pool_cap"] = cap
                cache[cap] = agg[BASELINE_ID]
            matched[scenario.id] = cache[cap]
        matched[BASELINE_ID] = cache[base_cap]

    pool_table = pool_effect_rows(aggregates, matched)
    return {"runs": all_runs, "scenarios": aggregates, "pool_effect": pool_table}


# --------------------------------------------------------------------------- #
# 6. CLI
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="ICU 床位调度 · 6 场景 × N seed 的 ε 网格 / HV / B_pool 运行器"
    )
    p.add_argument(
        "--scenarios",
        default="all",
        help="逗号分隔的场景 id（默认 all = 6 个内置场景）",
    )
    p.add_argument("--seeds", type=int, default=5, help="seed 个数（0..N-1，默认 5）")
    p.add_argument("--levels", type=int, default=3, help="ε 网格水平数（默认 3）")
    p.add_argument("--max-time", type=float, default=30.0, help="单次求解墙钟秒（默认 30）")
    p.add_argument(
        "--max-patients",
        type=int,
        default=200,
        help="候选池上限（默认 200；>100 需 AIGC_MIMIC_ALLOW=1）",
    )
    p.add_argument(
        "--max-points",
        type=int,
        default=None,
        help="可选：每场景每 seed 的 ε 网格求解数上限（debug 用）",
    )
    p.add_argument(
        "--source",
        default="db",
        choices=["db", "synthetic"],
        help="候选池来源：db（MIMIC/RDS，默认）或 synthetic（仓内合成，不读 MIMIC）",
    )
    p.add_argument("--out", default=None, help=f"输出 JSON（默认 {DEFAULT_OUT}）")
    p.add_argument("--smoke", action="store_true", help="快速自检：合成池 30 候选 / 1 seed / levels 2")
    p.add_argument("--verbose", action="store_true", help="打印每个 ε 格点的进度")
    p.add_argument(
        "--no-deterministic",
        action="store_true",
        help="不强制 num_search_workers=1（默认强制，保证可复现）",
    )
    return p


def resolve_cli_config(args: argparse.Namespace) -> dict[str, Any]:
    """把 CLI 参数解析成网格配置（``--smoke`` 覆盖为最小配置）。"""
    smoke = bool(args.smoke)
    if args.scenarios.strip().lower() in ("all", ""):
        ids = None
    else:
        ids = args.scenarios.split(",")
    scenarios = get_scenarios([BASELINE_ID] if smoke else ids)
    levels = 2 if smoke else int(args.levels)
    seeds = 1 if smoke else int(args.seeds)
    source = "synthetic" if smoke else str(args.source)
    max_time = min(float(args.max_time), SMOKE_MAX_TIME) if smoke else float(args.max_time)
    max_patients = SMOKE_POOL_CAP if smoke else int(args.max_patients)
    out = Path(args.out) if args.out else (SMOKE_OUT if smoke else DEFAULT_OUT)
    config = {
        "smoke": smoke,
        "source": source,
        "scenarios": [s.id for s in scenarios],
        "seeds": list(range(seeds)),
        "levels": levels,
        "max_time_seconds": max_time,
        "max_patients": max_patients,
        "max_points": args.max_points,
        "deterministic": not args.no_deterministic,
        "out": str(out),
        "candidate_hard_cap": CANDIDATE_HARD_CAP,
        "allow_env": ALLOW_ENV,
        "seed_effect": (
            "synthetic_pool_only（db 源下 seed 只影响 CP-SAT random_seed，池同源）"
        ),
        "objectives": "moo_phase3.DEFAULT_OBJECTIVES（7 目标）",
        "grid_objectives": "moo_phase3.DEFAULT_GRID_OBJECTIVES（4 目标 ε 网格）",
        "primary": "wait(priority_served)",
    }
    return {
        "config": config,
        "scenarios": scenarios,
        "seeds": config["seeds"],
        "levels": levels,
        "max_time": max_time,
        "max_patients": max_patients,
        "source": source,
        "out": out,
    }


def main(argv: Sequence[str] | None = None, *, env: Mapping[str, str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(F1_GATE, flush=True)

    try:
        cfg = resolve_cli_config(args)
        validate_grid_args(
            levels=cfg["levels"],
            seeds=len(cfg["seeds"]),
            max_time=cfg["max_time"],
            max_patients=cfg["max_patients"],
            scenarios=cfg["scenarios"],
        )
        caps = [effective_pool_cap(s, cfg["max_patients"]) for s in cfg["scenarios"]]
        gate = enforce_mimic_gate(
            source=cfg["source"],
            candidate_cap=max(caps),
            smoke=cfg["config"]["smoke"],
            env=os.environ if env is None else env,
        )
    except ValueError as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False))
        return 2

    cfg["config"]["gate"] = gate

    progress = None
    if args.verbose:

        def progress(i: int, n: int, bounds: Mapping[str, Any]) -> None:
            print(f"[grid] {i}/{n} bounds={dict(bounds)}", flush=True)

    payload = run_grid(
        scenarios=cfg["scenarios"],
        seeds=cfg["seeds"],
        levels=cfg["levels"],
        max_time=cfg["max_time"],
        max_patients=cfg["max_patients"],
        source=cfg["source"],
        max_points=cfg["config"]["max_points"],
        deterministic=cfg["config"]["deterministic"],
        progress=progress,
    )

    out = Path(cfg["out"])
    out.parent.mkdir(parents=True, exist_ok=True)
    document = {"config": cfg["config"], **payload}
    out.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "done",
                "out": str(out),
                "n_runs": len(payload["runs"]),
                "scenarios": {
                    sid: {
                        "hv_mean": round(agg["hv_mean"], 6),
                        "hv_std": round(agg["hv_std"], 6),
                        "high_risk_mean": round(agg["high_risk_mean"], 3),
                    }
                    for sid, agg in payload["scenarios"].items()
                },
                "pool_effect_summary": payload["pool_effect"]["summary"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
