"""H5: Predict-then-Optimize decision-quality ablation (pure helpers + runner).

Compares SOFA-only / formula / GBDT priorities on the *same* stay pool by
injecting priority_overrides into CP-SAT — proves allocation outcomes change,
not just Spearman correlation. Does NOT read decision risk_score.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def build_priority_maps(
    rows: Sequence[Mapping[str, Any]],
    *,
    gbdt_preds: Mapping[int, float] | None = None,
) -> dict[str, dict[int, float]]:
    """stay_id → weight for three in-repo urgency models."""
    sofa_only: dict[int, float] = {}
    formula: dict[int, float] = {}
    gbdt: dict[int, float] = {}
    for r in rows:
        sid = int(r["stay_id"])
        sofa = float(r.get("sofa_total") or 0.0)
        los = float(r.get("los_hours") or 0.0)
        sofa_only[sid] = 1.0 + sofa / 10.0
        formula[sid] = 1.0 + sofa / 10.0 + 2.0 / (1.0 + max(los, 1.0))
        if gbdt_preds and sid in gbdt_preds:
            gbdt[sid] = float(gbdt_preds[sid])
        else:
            gbdt[sid] = formula[sid]
    return {"sofa_only": sofa_only, "formula": formula, "gbdt": gbdt}


def assignment_set(result: Mapping[str, Any]) -> frozenset[int]:
    """Assigned stay_ids from a CP-SAT result."""
    ids = []
    for a in result.get("top_assignments") or []:
        try:
            ids.append(int(a["stay_id"]))
        except (KeyError, TypeError, ValueError):
            continue
    return frozenset(ids)


def decision_delta(
    sets: Mapping[str, frozenset[int]],
    *,
    reference: str = "formula",
) -> dict[str, Any]:
    """Jaccard / exclusive counts vs a reference priority model."""
    ref = sets.get(reference) or frozenset()
    out: dict[str, Any] = {"reference": reference}
    for name, s in sets.items():
        if name == reference:
            continue
        inter = len(ref & s)
        union = len(ref | s) or 1
        out[name] = {
            "jaccard_vs_ref": round(inter / union, 4),
            "only_in_ref": len(ref - s),
            "only_in_alt": len(s - ref),
            "n_assigned": len(s),
        }
    return out


def pto_takeaways(
    rows: Sequence[Mapping[str, Any]],
    deltas: Mapping[str, Any],
) -> list[str]:
    notes: list[str] = [
        "H5：同池、同硬约束下换紧迫度模型，看分床结果是否变化（决策质量，不只相关性）。"
    ]
    sofa = deltas.get("sofa_only") or {}
    j = sofa.get("jaccard_vs_ref")
    if j is not None:
        if float(j) < 0.999:
            notes.append(
                f"SOFA-only 与公式参考的分配集合 Jaccard={j}："
                "预测层差异已传导到分床决策。"
            )
        else:
            notes.append(
                "本池上 SOFA-only 与公式分配集合几乎重合："
                "小池/床位紧时决策可能对优先级不敏感——也要如实报告。"
            )
    hrs = [r.get("high_risk") for r in rows if r.get("high_risk") is not None]
    if len(set(hrs)) > 1:
        notes.append("不同优先级下 high_risk 服务数不同：词典序/加权目标受紧迫度排序影响。")
    notes.append("不接 decision risk_score；不宣称 online MIMIC-PPO。")
    return notes
