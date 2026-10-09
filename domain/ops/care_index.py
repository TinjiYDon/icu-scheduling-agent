"""H7 companion indices: CARE and UHRM (pure, no DB).

CARE — Clinical Allocation Risk-Equity index
UHRM — Unserved High-Risk Mass (priority mass of unassigned SOFA≥10)

These are project-defined evaluation indices for ICU bed assignment reports,
not replacements for SOFA itself.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

HIGH_RISK_SOFA = 10


def is_high_risk(sofa: float | int | None, *, threshold: int = HIGH_RISK_SOFA) -> bool:
    try:
        return float(sofa or 0.0) >= float(threshold)
    except (TypeError, ValueError):
        return False


def unserved_high_risk_mass(
    candidates: Sequence[Mapping[str, Any]],
    assigned_stay_ids: Sequence[int] | set[int],
    *,
    sofa_key: str = "sofa_total",
    weight_key: str = "priority_weight",
    id_key: str = "stay_id",
    threshold: int = HIGH_RISK_SOFA,
) -> dict[str, float]:
    """Sum of priority weights for high-risk patients left unassigned."""
    assigned = {int(x) for x in assigned_stay_ids}
    uhrm = 0.0
    pool_w = 0.0
    n_hr = 0
    n_hr_unassigned = 0
    for row in candidates:
        try:
            sofa = float(row.get(sofa_key) or 0.0)
            w = float(row.get(weight_key) or 0.0)
            sid = int(row[id_key])
        except (KeyError, TypeError, ValueError):
            continue
        if not is_high_risk(sofa, threshold=threshold):
            continue
        n_hr += 1
        pool_w += max(w, 0.0)
        if sid not in assigned:
            uhrm += max(w, 0.0)
            n_hr_unassigned += 1
    return {
        "uhrm": round(uhrm, 6),
        "uhrm_pool_weight": round(pool_w, 6),
        "n_high_risk_pool": float(n_hr),
        "n_high_risk_unassigned": float(n_hr_unassigned),
    }


def compute_care(
    *,
    high_risk_assigned: int | float,
    n_high_risk_pool: int | float,
    overload: int | float,
    uhrm: float,
    uhrm_pool_weight: float,
    alpha: float = 0.35,
    beta: float = 0.35,
    sofa_scale: float = float(HIGH_RISK_SOFA),
) -> dict[str, float]:
    """CARE = cover - α·overload_norm - β·uhrm_norm ∈ (-∞, 1].

    cover = (# high-risk assigned) / (# high-risk in pool)
    overload_norm = overload / (sofa_scale · max(high_risk_assigned, 1))
    uhrm_norm = UHRM / max(pool high-risk weight, ε)
    """
    pool = max(float(n_high_risk_pool), 0.0)
    hr_a = max(float(high_risk_assigned), 0.0)
    cover = (hr_a / pool) if pool > 0 else 1.0
    ov = max(float(overload), 0.0)
    ov_norm = ov / max(float(sofa_scale) * max(hr_a, 1.0), 1.0)
    mass_den = max(float(uhrm_pool_weight), 1e-9)
    uhrm_norm = max(float(uhrm), 0.0) / mass_den
    care = cover - float(alpha) * ov_norm - float(beta) * uhrm_norm
    return {
        "care": round(care, 6),
        "care_cover": round(cover, 6),
        "care_overload_norm": round(ov_norm, 6),
        "care_uhrm_norm": round(uhrm_norm, 6),
        "uhrm": round(float(uhrm), 6),
        "alpha": float(alpha),
        "beta": float(beta),
    }


def care_from_assignment_result(
    result: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    *,
    alpha: float = 0.35,
    beta: float = 0.35,
) -> dict[str, float]:
    """Build CARE/UHRM from a ``run_assignment``-like result + candidate rows."""
    assigned_ids = [
        int(a["stay_id"])
        for a in (result.get("top_assignments") or [])
        if a.get("stay_id") is not None
    ]
    mass = unserved_high_risk_mass(candidates, assigned_ids)
    values = dict((result.get("multiobjective") or {}).get("values") or {})
    hr = values.get("high_risk")
    if hr is None:
        hr = sum(
            1
            for a in (result.get("top_assignments") or [])
            if is_high_risk(a.get("sofa_total"))
        )
    overload = values.get("overload", 0)
    return compute_care(
        high_risk_assigned=int(hr or 0),
        n_high_risk_pool=int(mass["n_high_risk_pool"]),
        overload=int(overload or 0),
        uhrm=float(mass["uhrm"]),
        uhrm_pool_weight=float(mass["uhrm_pool_weight"]),
        alpha=alpha,
        beta=beta,
    )
