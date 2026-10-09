"""Per-scenario epsilon bound recalibration for stress packs."""

from __future__ import annotations

from typing import Any, Mapping, Protocol


DEFAULT_EPSILON_BOUNDS: dict[str, int] = {
    "occupancy": 10,
    "high_risk": 6,
    "overload": 42,
    "balance": 2,
}


class _ScenarioLike(Protocol):
    pool: str
    resource_overrides: dict[str, Any]


def scenario_epsilon_bounds(
    scenario: _ScenarioLike,
    *,
    base: Mapping[str, int] | None = None,
) -> dict[str, int]:
    """Loosen mid-grid ε when beds/iso/vent shrink so mid-point stays feasible more often."""
    bounds = dict(base or DEFAULT_EPSILON_BOUNDS)
    overrides = dict(scenario.resource_overrides or {})
    n_beds = int(overrides.get("n_beds", 20))
    n_iso = overrides.get("n_isolation_beds")
    n_vent = overrides.get("n_ventilators")

    bounds["occupancy"] = max(1, min(int(bounds.get("occupancy", 10)), max(1, n_beds // 2)))
    bounds["high_risk"] = max(0, min(int(bounds.get("high_risk", 6)), max(0, n_beds // 3)))

    stress = n_beds < 20 or n_iso is not None or n_vent is not None or scenario.pool != "default"
    if stress:
        bounds["overload"] = max(int(bounds.get("overload", 42)), 120)
        bounds["balance"] = max(int(bounds.get("balance", 2)), 8)
    if scenario.pool == "high_sofa":
        bounds["occupancy"] = max(1, min(bounds["occupancy"], 5))
        bounds["high_risk"] = max(0, min(bounds["high_risk"], 5))
        bounds["overload"] = max(bounds["overload"], 200)
    if scenario.pool == "zone_skew":
        bounds["occupancy"] = 1
        bounds["high_risk"] = 0
        bounds["balance"] = max(bounds["balance"], 20)
        bounds["overload"] = max(bounds["overload"], 200)
    # Ventilator shortage often makes mid occupancy/high_risk infeasible
    if n_vent is not None and int(n_vent) <= 2:
        bounds["occupancy"] = max(1, min(bounds["occupancy"], 4))
        bounds["high_risk"] = max(0, min(bounds["high_risk"], 2))
        bounds["overload"] = max(bounds["overload"], 200)
    return bounds
