"""H6: summarize rolling reoptimize vs greedy-admit-only contrast."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def _mean_history(history: Sequence[Mapping[str, Any]], key: str) -> float:
    vals = [float(h.get(key) or 0.0) for h in history]
    if not vals:
        return 0.0
    return round(sum(vals) / len(vals), 4)


def summarize_rolling_run(result: Mapping[str, Any]) -> dict[str, Any]:
    history = list(result.get("history") or [])
    return {
        "reoptimize": bool(result.get("reoptimize", True)),
        "final_occupancy": result.get("final_occupancy"),
        "bed_utilization_pct": result.get("bed_utilization_pct"),
        "total_admissions": result.get("total_admissions"),
        "total_discharges": result.get("total_discharges"),
        "mean_avg_sofa": _mean_history(history, "avg_sofa"),
        "mean_avg_weight": _mean_history(history, "avg_weight"),
        "mean_occupied": _mean_history(history, "occupied"),
    }


def rolling_contrast_takeaways(
    rolling: Mapping[str, Any],
    static: Mapping[str, Any],
) -> list[str]:
    notes = [
        "H6：同入出转随机种子下，对比「每步 CP-SAT 再优化」与「只贪心填空床」。"
    ]
    r_sofa = float(rolling.get("mean_avg_sofa") or 0)
    s_sofa = float(static.get("mean_avg_sofa") or 0)
    r_w = float(rolling.get("mean_avg_weight") or 0)
    s_w = float(static.get("mean_avg_weight") or 0)
    if r_sofa > s_sofa + 0.05:
        notes.append(
            f"滚动再优化的时段平均 SOFA（{r_sofa}）高于贪心填床（{s_sofa}）："
            "重优化更倾向保留/收治更重患者。"
        )
    elif abs(r_sofa - s_sofa) <= 0.05:
        notes.append(
            "本设定下平均 SOFA 接近：滚动增益可能主要体现在权重/周转，而非病情均值。"
        )
    else:
        notes.append(
            "本跑次滚动平均 SOFA 未高于贪心——如实报告，避免只挑好看实验。"
        )
    if r_w > s_w + 0.01:
        notes.append(
            f"滚动平均 priority 权重更高（{r_w} vs {s_w}）：再优化在目标函数上有增益。"
        )
    notes.append("不宣称 online MIMIC-PPO；滚动增益是仿真协议内的对照，非床旁 RCT。")
    return notes
