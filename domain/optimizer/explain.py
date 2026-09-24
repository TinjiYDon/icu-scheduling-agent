"""Explainable output for CP-SAT scheduling decisions (PLAN §6.3).

Produces per-patient justification, constraint binding analysis,
and objective decomposition — no SHAP dependency.
"""

from __future__ import annotations


def explain_assignment(result: dict) -> str:
    """Generate a human-readable explanation from a CP-SAT run result.

    Args:
        result: the dict returned by run_assignment()

    Returns:
        Multi-line formatted explanation string.
    """
    lines = []
    lines.append("=" * 65)
    lines.append("  ICU 床位调度 — 可解释性报告")
    lines.append("=" * 65)
    lines.append(f"  运行 ID       : {result.get('run_id', '?')}")
    lines.append(f"  求解状态      : {result.get('solver_status', '?')}")
    lines.append(
        f"  分配/候选     : {result['assigned']}/{result.get('n_stays', '?')}"
        f"  (床位: {result['n_beds']})"
    )
    mode = result.get("objective_mode")
    if mode:
        lines.append(f"  多目标模式    : {mode}")
    rules = result.get("constraint_rules") or {}
    if rules:
        lines.append(
            "  约束需求规则  : "
            f"iso={rules.get('isolation_mode')} · vent={rules.get('ventilator_mode')}"
            f"（pct={rules.get('ventilator_hash_pct')}）"
        )
        if rules.get("disclosure"):
            lines.append(f"  规则披露      : {str(rules['disclosure']).strip()[:120]}")
    demand = result.get("constraint_demand") or {}
    if demand:
        lines.append(
            f"  需求标记计数  : iso={demand.get('n_isolation_demand')} · "
            f"vent={demand.get('n_ventilator_demand')}"
        )
    lines.append("")

    lam = result.get("lambda") or {}
    obj = result.get("objective", {})
    sem = result.get("objective_semantics") or {}
    wait_note = (sem.get("wait") or {}).get("canonical", "priority_served")
    over_note = (sem.get("overload") or {}).get(
        "canonical", "high_risk_on_regular_beds"
    )

    lines.append("─" * 50)
    lines.append("  ① 目标函数分解")
    lines.append("─" * 50)
    lines.append(
        f"  f₀ 床位占用            : {obj.get('f0_occupancy', 0):>8.0f}"
        f"  (λ={float(lam.get('occupancy', 0)):.2f})"
    )
    lines.append(
        f"  f₀b 高危已服务         : {obj.get('f0b_high_risk_served', 0):>8.0f}"
        f"  (λ={float(lam.get('high_risk', 0)):.2f})"
    )
    lines.append(
        f"  f₁ 优先级服务合计      : {obj.get('f1_priority_total', 0):>8.0f}"
        f"  (λ.wait={float(lam.get('wait', 0)):.2f} · canonical={wait_note})"
    )
    lines.append(
        f"  f₂ 高危落普通床 SOFA   : {obj.get('f2_overload_penalty', 0):>8.0f}"
        f"  (λ.overload={float(lam.get('overload', 0)):.2f} · {over_note})"
    )
    lines.append(
        f"  f₃ 分区利用率差        : {obj.get('f3_balance_deviation', 0):>8.0f}"
        f"  (λ={float(lam.get('balance', 0)):.2f})"
    )
    lines.append(
        f"  f₄ 科室错配数          : {obj.get('f4_zone_mismatch', 0):>8.0f}"
        f"  (λ={float(lam.get('zone_mismatch', 0)):.2f})"
    )
    if "f5_move_penalty" in obj:
        lines.append(
            f"  f₅ 换床数              : {obj.get('f5_move_penalty', 0):>8.0f}"
        )
    zones = obj.get("zone_loads", [])
    labels = obj.get("zone_load_labels") or []
    if zones:
        if labels and len(labels) == len(zones):
            ztxt = ", ".join(f"{lb}={v}" for lb, v in zip(labels, zones, strict=True))
            lines.append(f"  各区负载: {ztxt}  (标准化利用率差目标)")
        else:
            lines.append(f"  各区负载: {zones}  (标准化利用率差目标)")
    lines.append("")

    res = result.get("resources", {})
    lines.append("─" * 50)
    lines.append("  ② 资源使用 & 约束绑定")
    lines.append("─" * 50)
    lines.append(f"  隔离病床  : {res.get('isolation_beds_used', '?')}")
    lines.append(f"  呼吸机    : {res.get('ventilators_used', '?')}")
    lines.append(f"  科室匹配  : {res.get('zone_matches', '?')}")
    ev = result.get("evaluation") or {}
    if "high_risk_on_regular" in ev:
        lines.append(
            f"  高危落普通床: {ev.get('high_risk_on_regular')} 人 · "
            f"SOFA累加={ev.get('high_risk_on_regular_sofa', ev.get('overload_penalty'))}"
        )
    lines.append("")

    assignments = result.get("top_assignments", [])
    if assignments:
        lines.append("─" * 50)
        lines.append("  ③ 分配详情 (前 10 位)")
        lines.append("─" * 50)
        header = (
            f"  {'患者ID':>10}  {'床号':>4} {'床区':>5} {'患者科':>5} {'匹配':>4}"
            f"  {'权重':>6}  {'SOFA':>5}  {'理由'}"
        )
        lines.append(header)
        lines.append("  " + "-" * 68)

        for a in assignments[:10]:
            reasons = []
            if a.get("needs_iso"):
                reasons.append("需隔离")
            if a.get("needs_vent"):
                reasons.append("需呼吸机")
            match = a.get("zone_match", True)
            if not match:
                reasons.append(f"跨科({a.get('patient_zone', '?')})")
            w = float(a.get("priority_weight", 0))
            if w >= 3.0:
                reasons.append("高优先级")
            elif w >= 2.0:
                reasons.append("中优先级")
            s = float(a.get("sofa_total", 0))
            if s >= 10:
                reasons.append(f"高危SOFA={s:.0f}")
                if str(a.get("bed_type", "")).upper() != "ISO":
                    reasons.append("计入overload")
            elif s >= 4:
                reasons.append(f"SOFA={s:.0f}")
            reason_str = ", ".join(reasons) if reasons else "基础权重"

            line = (
                f"  {a['stay_id']:>10}  {a['bed_id']:>4} {a['bed_type']:>5} "
                f"{a.get('patient_zone', '?'):>5} {'✓' if match else '✗':>4}"
                f"  {w:>6.3f}  {s:>5.1f}  {reason_str}"
            )
            lines.append(line)

        if len(assignments) > 10:
            lines.append(f"  ... 还有 {len(assignments) - 10} 条分配")

    lines.append("")
    lines.append("─" * 50)
    lines.append("  ④ 约束绑定分析")
    lines.append("─" * 50)

    n_assigned = result.get("assigned", 0)
    bindings = _analyze_constraints(result)
    for label, bind, detail in bindings:
        status = "▇ 绑定" if bind else "○ 松弛"
        lines.append(f"  [{status}] {label}: {detail}")

    lines.append("")
    lines.append("─" * 50)
    total_w = sum(float(a.get("priority_weight", 0)) for a in assignments)
    lines.append(f"  入选患者总权重(priority_served): {total_w:.2f}")
    lines.append(f"  平均权重: {total_w / max(n_assigned, 1):.3f}")
    lines.append("=" * 65)

    return "\n".join(lines)


def _analyze_constraints(result: dict) -> list[tuple[str, bool, str]]:
    """Check which constraints are binding (tight)."""
    bindings = []
    n_assigned = result.get("assigned", 0)
    n_beds = result.get("n_beds", 20)
    iso_used = result.get("resources", {}).get("isolation_beds_used", "0/4")
    vent_used = result.get("resources", {}).get("ventilators_used", "0/8")

    bind = n_assigned >= n_beds
    bindings.append(
        (
            "床位上限",
            bind,
            f"{n_assigned}/{n_beds} 已满" if bind else f"{n_assigned}/{n_beds} 有余量",
        )
    )

    iso_parts = iso_used.split("/")
    iso_u = int(iso_parts[0]) if len(iso_parts) == 2 else 0
    iso_t = int(iso_parts[1]) if len(iso_parts) == 2 else 4
    bind = iso_u >= iso_t
    bindings.append(
        ("隔离床位", bind, f"{iso_u}/{iso_t} 已满" if bind else f"{iso_u}/{iso_t}")
    )

    vent_parts = vent_used.split("/")
    v_u = int(vent_parts[0]) if len(vent_parts) == 2 else 0
    v_t = int(vent_parts[1]) if len(vent_parts) == 2 else 8
    bind = v_u >= v_t
    bindings.append(
        ("呼吸机", bind, f"{v_u}/{v_t} 已满" if bind else f"{v_u}/{v_t}")
    )

    zones = result.get("objective", {}).get("zone_loads", [])
    if zones:
        max_z = max(zones)
        min_z = min(zones)
        bind = (max_z - min_z) <= 1
        bindings.append(
            (
                "区域均衡",
                bind,
                f"max-min={max_z - min_z}" if not bind else "均衡 (max-min≤1)",
            )
        )

    return bindings


if __name__ == "__main__":
    import argparse

    from domain.optimizer.cp_sat import run_assignment

    parser = argparse.ArgumentParser(description="生成 ICU 调度可解释性报告")
    parser.add_argument(
        "--split",
        choices=["calib", "eval"],
        default=None,
        help="限制候选到 calib/eval 子集（默认全量候选）",
    )
    parser.add_argument(
        "--persist",
        action="store_true",
        help="写入 sched.assignments（默认不写，仅解释）",
    )
    args = parser.parse_args()

    result = run_assignment(split=args.split, persist=args.persist)
    print(explain_assignment(result))
