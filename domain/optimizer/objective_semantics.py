"""Canonical objective semantics for S2-MOO phase 2 (honest naming).

Lambda / ObjectiveSpec keys stay ``wait`` / ``overload`` for API compatibility.
Canonical clinical names are exposed via ``OBJECTIVE_SEMANTICS`` and evaluation
fields so reports do not imply wall-clock wait or undifferentiated bed SOFA load.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

HIGH_RISK_SOFA = 10

# Lambda key → canonical meaning (phase-2 disclosure)
OBJECTIVE_SEMANTICS: dict[str, dict[str, str]] = {
    "occupancy": {
        "canonical": "beds_filled",
        "sense": "max",
        "meaning": "已分配患者数（在硬约束下尽量铺满床）",
    },
    "high_risk": {
        "canonical": "high_risk_served",
        "sense": "max",
        "meaning": f"已分配且 SOFA>={HIGH_RISK_SOFA} 的患者数",
    },
    "wait": {
        "canonical": "priority_served",
        "sense": "max",
        "meaning": "已分配患者 priority_weight 总和（非真实等待时长）",
    },
    "overload": {
        "canonical": "high_risk_on_regular_beds",
        "sense": "min",
        "meaning": (
            f"SOFA>={HIGH_RISK_SOFA} 且分到非隔离床的 SOFA 累加"
            "（acuity 错配负荷；低危占普通床不计）"
        ),
    },
    "zone_mismatch": {
        "canonical": "non_preferred_zone_assignments",
        "sense": "min",
        "meaning": "非偏好科室分配数（隔离床匹配不计）",
    },
    "move": {
        "canonical": "bed_moves",
        "sense": "min",
        "meaning": "已在床患者换床数",
    },
    "balance": {
        "canonical": "zone_utilization_gap",
        "sense": "min",
        "meaning": "按配置床区标准化利用率 max−min 差",
    },
}


def is_high_risk_sofa(sofa: float | int) -> bool:
    return float(sofa) >= HIGH_RISK_SOFA


def overload_sofa_from_assignment(
    *,
    sofa: float | int,
    bed_type: str,
) -> int:
    """Per-assignment contribution to phase-2 overload (0 if not high-risk on REG)."""
    if not is_high_risk_sofa(sofa):
        return 0
    if str(bed_type).upper() == "ISO":
        return 0
    return int(float(sofa))


def sum_overload_from_assignments(assignments: Sequence[Mapping[str, Any]]) -> int:
    """Aggregate high-risk-on-regular SOFA load from assignment rows."""
    total = 0
    for row in assignments:
        total += overload_sofa_from_assignment(
            sofa=row.get("sofa_total", 0),
            bed_type=str(row.get("bed_type", "REG")),
        )
    return total


def count_high_risk_on_regular(assignments: Sequence[Mapping[str, Any]]) -> int:
    return sum(
        1
        for row in assignments
        if is_high_risk_sofa(row.get("sofa_total", 0))
        and str(row.get("bed_type", "REG")).upper() != "ISO"
    )
