"""Same-pool method bake-off helpers (pure summary; no DB)."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from domain.optimizer.moo_epsilon_recal import DEFAULT_EPSILON_BOUNDS


def epsilon_bounds_from_reference(
    values: Mapping[str, Any] | None,
    *,
    base: Mapping[str, int] | None = None,
) -> dict[str, int]:
    """Tighten/loosen mid ε from a feasible reference (usually weighted_sum values).

    Maximize objs → lower bound ≈ half of reference (still usually feasible).
    Minimize objs → upper bound ≈ 1.5× reference (or base floor).
    Avoids fixed DEFAULT_EPSILON_BOUNDS that assume ~20 occupancy on tiny pools.
    """
    bounds = dict(base or DEFAULT_EPSILON_BOUNDS)
    vals = dict(values or {})

    def _as_int(key: str, default: int = 0) -> int:
        try:
            return int(vals.get(key, default) or default)
        except (TypeError, ValueError):
            return default

    occ = _as_int("occupancy")
    hr = _as_int("high_risk")
    ol = _as_int("overload")
    bal = _as_int("balance", bounds.get("balance", 2))

    if occ > 0:
        bounds["occupancy"] = max(1, occ // 2)
    if hr >= 0 and "high_risk" in vals:
        bounds["high_risk"] = max(0, hr // 2)
    bounds["overload"] = max(int(bounds.get("overload", 42)), max(ol, 1) * 3 // 2, ol + 1)
    bounds["balance"] = max(int(bounds.get("balance", 2)), bal + 2 if bal else 2)
    return bounds


def flatten_bakeoff_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize one method result for tables / CSV."""
    values = dict(row.get("values") or {})
    return {
        "method": row.get("method"),
        "status": row.get("status"),
        "assigned": row.get("assigned"),
        "n_stays": row.get("n_stays"),
        "wall_time_seconds": row.get("wall_time_seconds"),
        "high_risk_wait": row.get("high_risk_wait"),
        "constraint_violations": row.get("constraint_violations"),
        "occupancy": values.get("occupancy"),
        "high_risk": values.get("high_risk"),
        "wait": values.get("wait"),
        "overload": values.get("overload"),
        "care": row.get("care"),
        "uhrm": row.get("uhrm"),
        "exact_hierarchy": row.get("exact_hierarchy"),
        "error": row.get("error"),
    }


def bakeoff_takeaways(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    """Short, defensible bullets for teachers (no overclaim)."""
    flat = [flatten_bakeoff_row(r) for r in rows]
    by_method = {str(r.get("method")): r for r in flat}
    notes: list[str] = []
    ws = by_method.get("weighted_sum") or {}
    lex = by_method.get("lexicographic") or {}
    eps = by_method.get("epsilon_mid") or {}
    greedy = by_method.get("greedy") or {}

    if all(r.get("status") in ("OPTIMAL", "FEASIBLE", "ok") for r in flat if r.get("method")):
        notes.append("同候选池上各方法均得到可行分配，说明硬约束模型可求解。")

    if ws.get("assigned") is not None and lex.get("assigned") is not None:
        if int(lex.get("high_risk") or 0) > int(ws.get("high_risk") or 0):
            notes.append(
                "词典序比加权和服务了更多高危（SOFA≥10）患者——体现优先级层级，不是换求解器。"
            )
        elif int(lex.get("high_risk") or 0) == int(ws.get("high_risk") or 0):
            notes.append("本池上词典序与加权和的高危服务数接近；差异可能主要在 wait/overload。")

    eps_status = str(eps.get("status") or "")
    eps_err = str(eps.get("error") or "")
    if "INFEASIBLE" in eps_status or "INFEASIBLE" in eps_err:
        notes.append("ε 边界过紧会不可解：说明底线约束在起作用，不是程序坏了。")
    elif eps.get("assigned") is not None and ws.get("assigned") is not None:
        if int(eps["assigned"]) < int(ws["assigned"]):
            notes.append("ε 中位解分配人数少于加权和：用底线约束换可解释的折中。")

    if greedy.get("assigned") is not None and ws.get("assigned") is not None:
        g, w = int(greedy["assigned"]), int(ws["assigned"])
        if g == w:
            notes.append(
                "贪心与加权 CP-SAT 分配人数相同：小池上启发式可能够用，不能据此说 RL/CP 更优。"
            )
        elif g < w:
            notes.append("加权 CP-SAT 比贪心多分配了床位：全局优化相对局部规则有增益。")

    rfcc = by_method.get("clinical_cascade") or {}
    if rfcc.get("care") is not None and ws.get("care") is not None:
        if float(rfcc["care"]) > float(ws["care"]) + 1e-6:
            notes.append(
                "H7 RFCC（clinical_cascade）的 CARE 指数高于加权和：稀缺门控下临床优先级联有效。"
            )
        elif rfcc.get("high_risk") is not None and ws.get("high_risk") is not None:
            if int(rfcc["high_risk"]) > int(ws["high_risk"]):
                notes.append("H7 RFCC 服务的高危人数多于加权和：风险优先序与占用优先序不同。")
            else:
                notes.append(
                    "H7 RFCC 已纳入对照；本池 CARE/高危差可能不明显——如实报告。"
                )
    elif rfcc.get("status") in ("OPTIMAL", "FEASIBLE", "ok"):
        notes.append("H7 RFCC（稀缺触发·风险优先临床级联）已跑通，作为相对 WS/Lex/ε 的新机理。")

    notes.append("本对照不宣称 online MIMIC-PPO；创新点是 RFCC 机理 + CARE/UHRM 指数，不是 OR-Tools 本身。")
    return notes
