"""MIMIC 网格运行器纯函数测试：无数据库 / 无 CP-SAT / 无网络。

只测 ``scripts/aigc_mimic_grid.py`` 的参数解析、汇总与同池反事实代数；
真正的求解只出现在验收命令 ``python scripts/aigc_mimic_grid.py --smoke`` 里。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.aigc_mimic_grid import (  # noqa: E402
    BASELINE_ID,
    CANDIDATE_HARD_CAP,
    SCENARIOS,
    aggregate_runs,
    build_parser,
    effective_pool_cap,
    enforce_mimic_gate,
    front_stats,
    get_scenarios,
    mean_std,
    pool_effect_rows,
    priority_overrides_for,
    resolve_cli_config,
    synthetic_pool,
    validate_grid_args,
)


# 1 — 场景定义 ---------------------------------------------------------------


def test_six_scenarios_defined():
    assert len(SCENARIOS) == 6
    ids = [s.id for s in SCENARIOS]
    assert ids == [
        "baseline",
        "more_beds",
        "fewer_vents",
        "more_iso",
        "small_pool",
        "high_acuity",
    ]
    by_id = {s.id: s for s in SCENARIOS}
    assert by_id["more_beds"].resource_overrides["n_beds"] == 24
    assert by_id["fewer_vents"].resource_overrides["n_ventilators"] == 4
    assert by_id["more_iso"].resource_overrides["n_isolation_beds"] == 8
    assert by_id["small_pool"].pool_cap == 50
    assert by_id["high_acuity"].priority_rule == "high_sofa"
    assert by_id[BASELINE_ID].resource_overrides == {}


def test_get_scenarios_validates_ids():
    assert [s.id for s in get_scenarios(None)] == [s.id for s in SCENARIOS]
    assert [s.id for s in get_scenarios(["baseline", "small_pool"])] == [
        "baseline",
        "small_pool",
    ]
    # 重复 id 去重、保序
    assert [s.id for s in get_scenarios(["small_pool", "small_pool"])] == ["small_pool"]
    with pytest.raises(ValueError):
        get_scenarios(["nope"])
    with pytest.raises(ValueError):
        get_scenarios([])


def test_effective_pool_cap():
    by_id = {s.id: s for s in SCENARIOS}
    assert effective_pool_cap(by_id["baseline"], 200) == 200
    assert effective_pool_cap(by_id["small_pool"], 200) == 50
    assert effective_pool_cap(by_id["small_pool"], 30) == 50  # 场景自带 cap 优先
    with pytest.raises(ValueError):
        effective_pool_cap(by_id["baseline"], 0)


# 2 — 合成池 ---------------------------------------------------------------


def test_synthetic_pool_deterministic_and_shaped():
    a = synthetic_pool(30, seed=0)
    b = synthetic_pool(30, seed=0)
    c = synthetic_pool(30, seed=1)
    assert a == b
    assert [r["stay_id"] for r in a] != [r["stay_id"] for r in c] or a != c
    assert len(a) == 30
    for row in a:
        assert set(row) == {"stay_id", "priority_weight", "sofa_total", "first_careunit"}
        # priority = 1 + sofa/10（仓内已实证的重编码关系）
        assert row["priority_weight"] == pytest.approx(1.0 + row["sofa_total"] / 10.0)
    # 排序口径：priority ↓, sofa ↓, stay_id ↑
    keys = [(-r["priority_weight"], -r["sofa_total"], r["stay_id"]) for r in a]
    assert keys == sorted(keys)
    with pytest.raises(ValueError):
        synthetic_pool(0, seed=0)


def test_priority_overrides_for_high_acuity():
    rows = [
        {"stay_id": 1, "priority_weight": 2.0, "sofa_total": 12.0, "first_careunit": "MICU"},
        {"stay_id": 2, "priority_weight": 1.2, "sofa_total": 2.0, "first_careunit": "CCU"},
    ]
    overrides = priority_overrides_for(rows, "high_sofa")
    assert overrides is not None
    assert set(overrides) == {1}
    assert overrides[1] > 2.0
    assert priority_overrides_for(rows, None) is None
    with pytest.raises(ValueError):
        priority_overrides_for(rows, "unknown_rule")


# 3 — 汇总统计 ---------------------------------------------------------------


def test_mean_std():
    mean, std = mean_std([0.1, 0.2, 0.3])
    assert mean == pytest.approx(0.2)
    assert std == pytest.approx(0.0816496580927726)  # 总体标准差 ddof=0
    assert mean_std([0.5]) == (0.5, 0.0)
    with pytest.raises(ValueError):
        mean_std([])
    with pytest.raises(ValueError):
        mean_std([0.1, float("nan")])


def _run(scenario: str, seed: int, **kwargs):
    base = {
        "scenario": scenario,
        "seed": seed,
        "n_feasible": 8,
        "n_front": 4,
        "hv": 0.5,
        "assigned": 20.0,
        "care": 5.0,
        "solve_time_sum": 1.0,
        "n_grid": 16,
        "pool_size": 200,
        "pool_cap": 200,
    }
    base.update(kwargs)
    return base


def test_aggregate_runs():
    runs = [
        _run("baseline", 0, hv=0.4, care=4.0),
        _run("baseline", 1, hv=0.6, care=6.0),
        _run("small_pool", 0, hv=0.7, pool_cap=50),
    ]
    agg = aggregate_runs(runs)
    assert set(agg) == {"baseline", "small_pool"}
    assert agg["baseline"]["n_seeds"] == 2
    assert agg["baseline"]["seeds"] == [0, 1]
    assert agg["baseline"]["hv_mean"] == pytest.approx(0.5)
    assert agg["baseline"]["hv_std"] == pytest.approx(0.1)
    assert agg["baseline"]["care_mean"] == pytest.approx(5.0)
    assert agg["small_pool"]["hv_std"] == 0.0
    assert agg["small_pool"]["pool_cap"] == 50
    for key in (
        "n_seeds",
        "seeds",
        "hv_mean",
        "hv_std",
        "care_mean",
        "care_std",
        "assigned_mean",
        "n_feasible_mean",
        "n_front_mean",
        "solve_time_sum_mean",
        "pool_cap",
    ):
        assert key in agg["baseline"]
    with pytest.raises(ValueError):
        aggregate_runs([])


def test_front_stats():
    empty = front_stats({"front": []})
    assert empty == {"assigned": 0.0, "care": 0.0}
    scan = {
        "front": [
            {"values": {"occupancy": 20, "high_risk": 4}},
            {"values": {"occupancy": 18, "high_risk": 6}},
        ]
    }
    stats = front_stats(scan)
    assert stats["assigned"] == pytest.approx(19.0)
    assert stats["care"] == pytest.approx(5.0)


# 4 — 同池反事实（B_pool）----------------------------------------------------


def _agg(hv: float, care: float, pool_cap: int = 200):
    return {"hv_mean": hv, "care_mean": care, "pool_cap": pool_cap}


def test_pool_effect_rows_keys_and_zero_for_same_pool():
    aggregates = {
        "baseline": _agg(0.50, 5.0),
        "more_beds": _agg(0.62, 5.4),
    }
    table = pool_effect_rows(aggregates, {})
    assert table["baseline"] == "baseline"
    assert table["baseline_hv_mean"] == pytest.approx(0.50)
    assert len(table["rows"]) == 1
    row = table["rows"][0]
    assert row["scenario"] == "more_beds"
    assert set(row["metrics"]) == {"hv", "care"}
    # 同池（未给 matched 差异）→ delta_match == delta_naive → pool_effect == 0
    assert row["metrics"]["hv"]["pool_effect"] == pytest.approx(0.0)
    assert row["metrics"]["hv"]["delta_naive"] == pytest.approx(0.12)
    # 汇总键齐全（来自 summarize_pool_effect）
    summary = table["summary"]
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
        assert key in summary
    assert summary["n_metrics"] == 1
    with pytest.raises(ValueError):
        pool_effect_rows({"more_beds": _agg(0.6, 5.0)}, {})


def test_pool_effect_rows_detects_pool_difference():
    """small_pool 只换池：baseline 在同一小池上重跑后才算得出纯池效应。"""
    aggregates = {
        "baseline": _agg(0.50, 5.0, pool_cap=200),
        "small_pool": _agg(0.70, 5.0, pool_cap=50),
    }
    matched = {"small_pool": _agg(0.65, 5.0, pool_cap=50)}
    table = pool_effect_rows(aggregates, matched)
    row = table["rows"][0]
    hv = row["metrics"]["hv"]
    assert hv["naive_a"] == pytest.approx(0.50)
    assert hv["naive_b"] == pytest.approx(0.70)
    assert hv["matched_a"] == pytest.approx(0.65)
    assert hv["delta_naive"] == pytest.approx(0.20)
    assert hv["delta_match"] == pytest.approx(0.05)
    assert hv["pool_effect"] == pytest.approx(0.15)
    assert hv["sign"] == "positive"
    assert row["B_pool_hv"] == pytest.approx(0.15)
    assert row["matched_pool_cap"] == 50
    assert table["summary"]["positive_share"] == pytest.approx(1.0)


# 5 — 参数校验 / F1 门 -------------------------------------------------------


def test_validate_grid_args_rejects_bad_input():
    scenarios = get_scenarios(["baseline"])
    ok = dict(levels=2, seeds=1, max_time=2.0, max_patients=30, scenarios=scenarios)
    validate_grid_args(**ok)
    for patch in (
        {"levels": 1},
        {"seeds": 0},
        {"max_time": 0.0},
        {"max_time": float("inf")},
        {"max_patients": 0},
        {"scenarios": []},
    ):
        with pytest.raises(ValueError):
            validate_grid_args(**{**ok, **patch})


def test_enforce_mimic_gate():
    assert enforce_mimic_gate(
        source="db", candidate_cap=CANDIDATE_HARD_CAP, smoke=False, env={}
    )
    assert enforce_mimic_gate(source="db", candidate_cap=50, smoke=False, env={})
    assert enforce_mimic_gate(source="db", candidate_cap=5000, smoke=True, env={})
    assert enforce_mimic_gate(source="synthetic", candidate_cap=5000, smoke=False, env={})
    assert enforce_mimic_gate(
        source="db", candidate_cap=5000, smoke=False, env={"AIGC_MIMIC_ALLOW": "1"}
    )
    with pytest.raises(ValueError):
        enforce_mimic_gate(source="db", candidate_cap=5000, smoke=False, env={})
    with pytest.raises(ValueError):
        enforce_mimic_gate(
            source="db", candidate_cap=5000, smoke=False, env={"AIGC_MIMIC_ALLOW": "0"}
        )


def test_resolve_cli_config_smoke_and_full():
    parser = build_parser()

    smoke = resolve_cli_config(parser.parse_args(["--smoke"]))
    assert smoke["config"]["smoke"] is True
    assert smoke["source"] == "synthetic"
    assert smoke["scenarios"][0].id == BASELINE_ID
    assert smoke["seeds"] == [0]
    assert smoke["levels"] == 2
    assert smoke["max_time"] <= 2.0
    assert smoke["max_patients"] == 30
    assert str(smoke["out"]).endswith("mimic_grid_smoke.json")

    full = resolve_cli_config(parser.parse_args([]))
    assert full["config"]["smoke"] is False
    assert full["source"] == "db"
    assert [s.id for s in full["scenarios"]] == [s.id for s in SCENARIOS]
    assert full["seeds"] == [0, 1, 2, 3, 4]
    assert full["levels"] == 3
    assert str(full["out"]).endswith("mimic_grid.json")

    subset = resolve_cli_config(
        parser.parse_args(["--scenarios", "baseline,small_pool", "--seeds", "2", "--levels", "2"])
    )
    assert [s.id for s in subset["scenarios"]] == ["baseline", "small_pool"]
    assert subset["seeds"] == [0, 1]
    assert subset["levels"] == 2
