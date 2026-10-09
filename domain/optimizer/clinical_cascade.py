"""H7: Scarcity-Triggered Risk-First Clinical Cascade (RFCC).

Innovation (ICU-specific mechanism, not a new generic solver):
  - When candidates exceed beds (scarcity), lexicographic priority becomes
    high_risk → overload(min) → wait → occupancy → … (clinical-first).
  - When beds are abundant, fall back to fill-first (occupancy → high_risk → …).
  - Standard weighted-sum / occupancy-first lex / ε do not encode this gate.

Companion index CARE / UHRM live in ``domain.ops.care_index``.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

# Scarcity gate: protect high-acuity coverage and acuity-matched beds first.
RISK_FIRST_ORDER: tuple[str, ...] = (
    "high_risk",
    "overload",
    "wait",
    "occupancy",
    "zone_mismatch",
    "move",
    "balance",
)

# Abundant beds: fill capacity first (classic OR occupancy-first lex).
FILL_FIRST_ORDER: tuple[str, ...] = (
    "occupancy",
    "high_risk",
    "wait",
    "overload",
    "zone_mismatch",
    "move",
    "balance",
)


def scarcity_triggered(
    n_patients: int,
    n_beds: int,
    *,
    margin: int = 0,
) -> bool:
    """True when demand meets/exceeds bed supply (competition for every bed).

    ``n >= B`` counts as scarcity: even 1:1 matching still forces triage among
    soft objectives — the clinically interesting case for RFCC.
    """
    return int(n_patients) + int(margin) >= int(n_beds)


def cascade_order(
    n_patients: int,
    n_beds: int,
    *,
    margin: int = 0,
    available: Sequence[str] | None = None,
) -> tuple[str, ...]:
    """Pick RFCC objective order under the scarcity gate."""
    order = (
        RISK_FIRST_ORDER
        if scarcity_triggered(n_patients, n_beds, margin=margin)
        else FILL_FIRST_ORDER
    )
    if available is None:
        return order
    allow = set(available)
    return tuple(name for name in order if name in allow)


def cascade_meta(
    n_patients: int,
    n_beds: int,
    *,
    margin: int = 0,
) -> dict[str, Any]:
    scarce = scarcity_triggered(n_patients, n_beds, margin=margin)
    return {
        "mechanism": "RFCC",
        "full_name": "Scarcity-Triggered Risk-First Clinical Cascade",
        "gate": "scarcity" if scarce else "abundant",
        "n_patients": int(n_patients),
        "n_beds": int(n_beds),
        "order": list(cascade_order(n_patients, n_beds, margin=margin)),
        "note": (
            "ICU-specific cascade: scarcity → risk/acuity first; "
            "abundant → occupancy first. Not a new CP solver."
        ),
    }


def filter_order_to_specs(
    order: Sequence[str],
    spec_names: Mapping[str, Any] | Sequence[str],
) -> list[str]:
    names = set(spec_names.keys() if hasattr(spec_names, "keys") else spec_names)
    return [n for n in order if n in names]
