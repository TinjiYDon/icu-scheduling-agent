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
        f"  分配/候选     : {result['assigned']}/{result.get('n_stays','?')}"
        f"  (床位: {result['n_beds']})"
    )
    lines.append("")

    # ── 1. Objective decomposition ──
    obj = result.get("objective", {})
    lines.append("─" * 50)
    lines.append("  ① 目标函数分解")
    lines.append("─" * 50)
    lines.append(
        f"  f₁ 高优先级加权等待  : {obj.get('f1_priority_total', 0):>8.0f}"
        f"  (权重 λ={10.0:.0f})"
    )
    lines.append(
        f"  f₂ 床位超负荷惩罚    : {obj.get('f2_overload_penalty', 0):>8.0f}"
        f"  (权重 λ={1.0:.0f})"
    )
    lines.append(
        f"  f₃ 区域均衡偏差      : {obj.get('f3_balance_deviation', 0):>8.0f}"
        f"  (权重 λ=0.1)"
    )
    lines.append(
        f"  f₄ 科室错配惩罚      : {obj.get('f4_zone_mismatch', 0):>8.0f}"
        f"  (50pts/人)"
    )
    zones = obj.get("zone_loads", [])
    if zones:
        lines.append(f"  各区负载: {zones}  (目标: 均匀分配)")
    lines.append("")

    # ── 2. Resource usage ──
    res = result.get("resources", {})
    lines.append("─" * 50)
    lines.append("  ② 资源使用 & 约束绑定")
    lines.append("─" * 50)
    lines.append(f"  隔离病床  : {res.get('isolation_beds_used', '?')}")
    lines.append(f"  呼吸机    : {res.get('ventilators_used', '?')}")
    lines.append(f"  科室匹配  : {res.get('zone_matches', '?')}")
    lines.append("")

    # ── 3. Per-assignment justification ──
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
                reasons.append(f"跨科({a.get('patient_zone','?')})")
            w = float(a.get("priority_weight", 0))
            if w >= 3.0:
                reasons.append("高优先级")
            elif w >= 2.0:
                reasons.append("中优先级")
            s = float(a.get("sofa_total", 0))
            if s >= 4:
                reasons.append(f"SOFA={s:.0f}")
            reason_str = ", ".join(reasons) if reasons else "基础权重"

            line = (
                f"  {a['stay_id']:>10}  {a['bed_id']:>4} {a['bed_type']:>5} {a.get('patient_zone','?'):>5} {'✓' if match else '✗':>4}"
                f"  {w:>6.3f}  {s:>5.1f}  {reason_str}"
            )
            lines.append(line)

        if len(assignments) > 10:
            lines.append(f"  ... 还有 {len(assignments) - 10} 条分配")

    # ── 4. Constraint binding analysis ──
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
    total_w = sum(
        float(a.get("priority_weight", 0)) for a in assignments
    )
    lines.append(f"  入选患者总权重: {total_w:.2f}")
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

    # Bed capacity
    bind = n_assigned >= n_beds
    bindings.append(
        ("床位上限", bind, f"{n_assigned}/{n_beds} 已满" if bind else f"{n_assigned}/{n_beds} 有余量")
    )

    # Isolation
    iso_parts = iso_used.split("/")
    iso_u = int(iso_parts[0]) if len(iso_parts) == 2 else 0
    iso_t = int(iso_parts[1]) if len(iso_parts) == 2 else 4
    bind = iso_u >= iso_t
    bindings.append(
        ("隔离床位", bind, f"{iso_u}/{iso_t} 已满" if bind else f"{iso_u}/{iso_t}")
    )

    # Ventilator
    vent_parts = vent_used.split("/")
    v_u = int(vent_parts[0]) if len(vent_parts) == 2 else 0
    v_t = int(vent_parts[1]) if len(vent_parts) == 2 else 8
    bind = v_u >= v_t
    bindings.append(
        ("呼吸机", bind, f"{v_u}/{v_t} 已满" if bind else f"{v_u}/{v_t}")
    )

    # Zone balance
    zones = result.get("objective", {}).get("zone_loads", [])
    if zones:
        max_z = max(zones)
        min_z = min(zones)
        bind = (max_z - min_z) <= 1
        bindings.append(
            ("区域均衡", bind, f"max-min={max_z-min_z}" if not bind else "均衡 (max-min=0)")
        )

    return bindings
