"""AIGC 语义可用性契约演示：DAC 校验 + FD 压测 + 同池反事实。

只跑合成数据；不读数据库、不跑 CP-SAT/MIMIC、不访问网络。
`reports/*.json` 若存在，只用来演示“把两组方法的同一指标喂进 pool_effect”。

    python scripts/aigc_contract_demo.py --n 200 --seed 0
    python scripts/aigc_contract_demo.py --n 64 --seed 3 --output reports/aigc/demo.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # 允许 `python scripts/aigc_contract_demo.py` 直接跑
    sys.path.insert(0, str(ROOT))

from domain.optimizer.data_contract import (  # noqa: E402
    ConstraintContract,
    FieldContract,
    check_contract,
    degrade_or_refuse,
)
from domain.optimizer.fd_stress import (  # noqa: E402
    KNOWN_FDS,
    field_alignment,
    make_synthetic_columns,
    ranking_stability,
    refusal_accuracy,
    spurious_dof,
)
from domain.optimizer.pool_effect import (  # noqa: E402
    decompose,
    pool_effect,
    summarize_pool_effect,
)

OUT = ROOT / "reports" / "aigc"


# --------------------------------------------------------------------------- #
# 1. 契约：原始表（有缺陷） vs 修复后表
# --------------------------------------------------------------------------- #


def raw_field_contracts() -> list[FieldContract]:
    return [
        FieldContract("sofa_total", "exact"),
        FieldContract("priority_weight", "heuristic", depends_on=("sofa_total",)),
        FieldContract("first_careunit", "exact"),
        FieldContract(
            "isolation_heuristic",
            "heuristic",
            depends_on=("first_careunit",),
            redundant_with=("first_careunit",),
        ),
        FieldContract("los_hours", "unit_error"),
        FieldContract("n_isolation_beds", "exact"),
    ]


def repaired_field_contracts() -> list[FieldContract]:
    return [
        FieldContract("sofa_total", "exact"),
        FieldContract("first_careunit", "exact"),
        FieldContract("isolation_heuristic", "heuristic", depends_on=("first_careunit",)),
        FieldContract("los_days", "exact"),
        FieldContract("n_isolation_beds", "exact"),
    ]


RAW_CONSTRAINTS = [
    ConstraintContract("priority_rank", ("priority_weight",), "排序错位：priority 只是 SOFA 重编码"),
    ConstraintContract(
        "isolation_capacity",
        ("isolation_heuristic", "n_isolation_beds"),
        "缺隔离床数 → 容量约束失效",
    ),
    ConstraintContract("los_window", ("los_hours",), "单位错 24×：LOS 窗口被放大"),
]

REPAIRED_CONSTRAINTS = [
    ConstraintContract("priority_rank", ("sofa_total",), "排序错位"),
    ConstraintContract("isolation_capacity", ("isolation_heuristic", "n_isolation_beds")),
    ConstraintContract("los_window", ("los_days",)),
]

FD_MAP = {name: deps for name, (_desc, deps) in KNOWN_FDS.items()}


def contract_scenarios(columns: dict) -> list[dict]:
    """raw（缺列 → refuse）/ degraded（只有冗余+单位错 → degrade）/ repaired（pass）。"""
    repaired_columns = [
        "stay_id",
        "sofa_total",
        "first_careunit",
        "isolation_heuristic",
        "los_days",
        "n_isolation_beds",
    ]
    scenarios = [
        {
            "name": "raw",
            "note": "原始表 + 原始契约：缺 n_isolation_beds，los_hours 单位错",
            "columns": columns,
            "contracts": raw_field_contracts() + RAW_CONSTRAINTS,
            "expect_refusal": True,
        },
        {
            "name": "degraded",
            "note": "原始表，但去掉容量约束：只剩冗余与单位错 → 降级可跑",
            "columns": columns,
            "contracts": raw_field_contracts()
            + [c for c in RAW_CONSTRAINTS if c.name != "isolation_capacity"],
            "expect_refusal": False,
        },
        {
            "name": "repaired",
            "note": "修复表：los_days 单位正确、隔离床数列补齐、冗余列剔除",
            "columns": repaired_columns,
            "contracts": repaired_field_contracts() + REPAIRED_CONSTRAINTS,
            "expect_refusal": False,
        },
    ]
    for item in scenarios:
        report = check_contract(item["contracts"], item["columns"], FD_MAP)
        item["report"] = report
        item["decision"] = degrade_or_refuse(report, policy="strict")
        item["decision_advisory"] = degrade_or_refuse(report, policy="advisory")
    return scenarios


# --------------------------------------------------------------------------- #
# 2. 三个 model_spec：naive / FD-audited / contract-aware
# --------------------------------------------------------------------------- #


def model_specs() -> list[dict]:
    return [
        {
            "name": "naive",
            "note": "priority+SOFA 同场、isolation+careunit 同场、los_hours 直接当小时",
            "variables": [
                {
                    "name": "x_priority",
                    "fields": ["priority_weight", "sofa_total"],
                }
            ],
            "constraints": [
                {"name": "iso", "fields": ["isolation_heuristic", "first_careunit"]},
                {"name": "los", "fields": ["los_hours", "n_beds"]},
            ],
        },
        {
            "name": "fd_audited",
            "note": "显式剔除冗余（excluded/derived），但字段名仍是原始列",
            "variables": [
                {
                    "name": "x_priority",
                    "fields": ["priority_weight"],
                    "excluded": ["sofa_total"],
                }
            ],
            "constraints": [
                {"name": "iso", "fields": ["isolation_heuristic"], "derived": ["first_careunit"]}
            ],
        },
        {
            "name": "contract_aware",
            "note": "只用契约里可用的原始字段 + 修复后的 los_days",
            "variables": [{"name": "x_sofa", "fields": ["sofa_total"]}],
            "constraints": [
                {"name": "iso", "fields": ["isolation_heuristic"]},
                {"name": "los", "fields": ["los_days"]},
            ],
        },
    ]


# --------------------------------------------------------------------------- #
# 3. 同池反事实
# --------------------------------------------------------------------------- #


def synthetic_pool_example() -> dict:
    """H7 口径示例：整池（不同 stay 子集）vs 同池，高风险管理增益。"""
    result = pool_effect(naive_a=0.62, naive_b=0.78, matched_a=0.63, matched_b=0.66)
    result.update(
        {
            "label": "H7 synthetic",
            "metric": "high_risk_assigned_rate (higher is better)",
            "decomposition": decompose(result["delta_naive"], result["delta_match"]),
            "note": "合成数字：仅演示代数，不代表 MIMIC 结果",
        }
    )
    return result


def report_pool_checks() -> list[dict]:
    """把 `reports/*.json` 里两组方法的同一指标喂进 pool_effect（若报告存在）。

    现有报告都是**共享池**（同 fair_pool、同 stay 列表），所以 naive 与 matched
    喂同一组数字，pool_effect 应为 0——这正好是口径自检：H5/H6/H7 的对照里
    池效应没有被分离出来。
    """
    checks: list[dict] = []

    path = ROOT / "reports" / "pto_decision_ablation.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = [r for r in data.get("rows", []) if isinstance(r, dict)]
        metric = "high_risk_waiting"
        values = {
            str(r["method"]): float(r[metric])
            for r in rows
            if isinstance(r.get("method"), str)
            and isinstance(r.get(metric), (int, float))
            and not isinstance(r.get(metric), bool)
        }
        for a, b in (("sofa_only", "formula"), ("sofa_only", "gbdt"), ("greedy", "weighted_sum")):
            if a in values and b in values:
                effect = pool_effect(values[a], values[b], values[a], values[b])
                effect.update(
                    {
                        "label": "H5/H7 report",
                        "metric": f"{metric} (lower is better)",
                        "source": str(path.relative_to(ROOT)),
                        "a_method": a,
                        "b_method": b,
                        "note": "共享池：naive 与 matched 同源，pool_effect 应为 0",
                    }
                )
                checks.append(effect)
                break
    except (OSError, ValueError, KeyError, TypeError):
        pass

    path = ROOT / "reports" / "rolling_contrast.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        naive = data.get("greedy_admit_only") or {}
        matched = data.get("rolling_reoptimize") or {}
        metric = "mean_avg_sofa"
        if isinstance(naive.get(metric), (int, float)) and isinstance(
            matched.get(metric), (int, float)
        ):
            effect = pool_effect(
                float(naive[metric]),
                float(matched[metric]),
                float(naive[metric]),
                float(matched[metric]),
            )
            effect.update(
                {
                    "label": "H6 report",
                    "metric": f"{metric} (lower is better)",
                    "source": str(path.relative_to(ROOT)),
                    "a_method": "greedy_admit_only",
                    "b_method": "rolling_reoptimize",
                    "note": "同入出转调度 → 共享池，pool_effect 应为 0",
                }
            )
            checks.append(effect)
    except (OSError, ValueError, KeyError, TypeError):
        pass

    return checks


# --------------------------------------------------------------------------- #
# 4. main
# --------------------------------------------------------------------------- #


def main() -> int:
    ap = argparse.ArgumentParser(description="AIGC contract / FD stress / pool-effect demo")
    ap.add_argument("--n", type=int, default=200, help="合成样本数（默认 200）")
    ap.add_argument("--seed", type=int, default=0, help="随机种子（默认 0）")
    ap.add_argument("--output", default="", help="输出 JSON（默认 reports/aigc/contract_demo.json）")
    args = ap.parse_args()

    if args.n < 1:
        ap.error("--n 必须 >= 1")

    columns = make_synthetic_columns(n=args.n, seed=args.seed)
    scenarios = contract_scenarios(columns)
    specs = model_specs()

    raw_contracts = raw_field_contracts() + RAW_CONSTRAINTS
    repaired_contracts = repaired_field_contracts() + REPAIRED_CONSTRAINTS

    # --- DAC ---
    print("## DAC（语义可用性契约）\n")
    print("| scenario | action(strict) | advisory | violations |")
    print("|---|---|---|---:|")
    for item in scenarios:
        report = item["report"]
        print(
            f"| {item['name']} | {item['decision']['action']} | "
            f"{item['decision_advisory']['action']} | {len(report.violations)} |"
        )
    print()
    for item in scenarios:
        print(f"- **{item['name']}**：{item['note']}")
        for v in item["report"].violations:
            print(f"  - {v}")
    print()

    refusal = refusal_accuracy(
        [item["report"] for item in scenarios],
        [item["expect_refusal"] for item in scenarios],
    )
    print(f"refusal_accuracy = {refusal:.3f}（raw 应拒答，degraded/repaired 不应）\n")

    # --- FD 压测 ---
    print("## FD 压测（伪自由度 / 契约对齐）\n")
    print("| model_spec | spurious_DoF | alignment(vs raw) | alignment(vs repaired) |")
    print("|---|---:|---:|---:|")
    spec_rows = []
    for spec in specs:
        dof = spurious_dof(spec, KNOWN_FDS)
        align_raw = field_alignment(spec, raw_contracts)
        align_fixed = field_alignment(spec, repaired_contracts)
        spec_rows.append(
            {
                "name": spec["name"],
                "note": spec["note"],
                "spurious_dof": dof,
                "alignment_raw": round(align_raw, 4),
                "alignment_repaired": round(align_fixed, 4),
            }
        )
        print(f"| {spec['name']} | {dof} | {align_raw:.3f} | {align_fixed:.3f} |")
    print()

    # 排序稳定性：SOFA 真序 vs priority 重编码序 / 隔离启发式序
    sofa = columns["sofa_total"]
    stability_perfect = ranking_stability(sofa, columns["priority_weight"], k=3)
    stability_proxy = ranking_stability(sofa, columns["isolation_heuristic"], k=3)
    print(
        f"ranking_stability(k=3): sofa vs priority = {stability_perfect:.3f}；"
        f"sofa vs isolation_heuristic = {stability_proxy:.3f}\n"
    )

    # --- pool effect ---
    print("## 同池反事实（pool effect）\n")
    synthetic = synthetic_pool_example()
    print("| example | metric | delta_naive | delta_match | pool_effect |")
    print("|---|---|---:|---:|---:|")
    print(
        f"| {synthetic['label']} | {synthetic['metric']} | "
        f"{synthetic['delta_naive']:.4f} | {synthetic['delta_match']:.4f} | "
        f"{synthetic['pool_effect']:.4f} |"
    )
    checks = report_pool_checks()
    for check in checks:
        print(
            f"| {check['label']} | {check['metric']} | "
            f"{check['delta_naive']:.4f} | {check['delta_match']:.4f} | "
            f"{check['pool_effect']:.4f} |"
        )
    print()
    print(
        f"B_pool(合成) = {synthetic['pool_effect']:.4f} → {synthetic['interpretation']}"
    )
    print(
        "decompose 恒等：pool + mechanism + interaction = "
        f"{synthetic['decomposition']['pool_effect']:.4f} + "
        f"{synthetic['decomposition']['mechanism_effect']:.4f} + "
        f"{synthetic['decomposition']['interaction']:.4f} = "
        f"{synthetic['delta_naive']:.4f}"
    )
    if checks:
        summary = summarize_pool_effect(
            {f"{c['label']}:{c['metric']}": c for c in checks}
            | {f"{synthetic['label']}:{synthetic['metric']}": synthetic}
        )
        print(f"summarize_pool_effect: {summary['dominant_sign']} / "
              f"mean_abs={summary['mean_abs_pool_effect']:.4f}")
    else:
        summary = summarize_pool_effect(
            {f"{synthetic['label']}:{synthetic['metric']}": synthetic}
        )
    print("注：报告侧 pool_effect = 0 说明现有 H5/H6/H7 对照是共享池，没有池污染可分离。\n")

    output = {
        "config": {
            "n": args.n,
            "seed": args.seed,
            "fd_map": {k: list(v) for k, v in FD_MAP.items()},
            "known_fds": {k: {"formula": v[0], "depends_on": list(v[1])} for k, v in KNOWN_FDS.items()},
            "policy": "strict",
        },
        "results": {
            "contracts": [
                {
                    "scenario": item["name"],
                    "note": item["note"],
                    "report": item["report"].as_dict(),
                    "decision_strict": item["decision"],
                    "decision_advisory": item["decision_advisory"],
                }
                for item in scenarios
            ],
            "refusal_accuracy": refusal,
            "model_specs": spec_rows,
            "ranking_stability_top3": {
                "sofa_vs_priority": stability_perfect,
                "sofa_vs_isolation_heuristic": stability_proxy,
            },
            "pool_effect": {
                "synthetic": synthetic,
                "report_checks": checks,
                "summary": summary,
            },
        },
        "note": "synthetic only; 外部 LLM 只喂合成数据；不构成临床证据",
    }

    path = Path(args.output) if args.output else OUT / "contract_demo.json"
    if not path.is_absolute():
        path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
