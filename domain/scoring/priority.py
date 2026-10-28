"""Priority construction for bed assignment.

Modes
-----
sofa_rule
    Legacy rule: ``w_i = 1 + sofa_i / 10``.  Exactly collinear with
    ``f0`` and ``f2``, kept only as a baseline.
composite
    ``w_i = 1 + sofa_weight * sofa_i / 12 + wait_weight * wait_norm_i``.
    ``wait_norm_i`` is the empirical percentile (0-1) of elapsed ICU time.
    Using a percentile instead of a capped ratio avoids saturation when most
    patients exceed the cap, which would leave the objective collinear again.
"""

from __future__ import annotations

from typing import Iterable, Mapping

SOFA_MAX = 12.0
PRIORITY_MODES = ("sofa_rule", "composite")


def sofa_rule(sofa_totals: Iterable[float]) -> list[float]:
    """Legacy priority: 1 + sofa / 10."""
    return [round(1.0 + float(s) / 10.0, 4) for s in sofa_totals]


def composite(
    sofa_totals: Iterable[float],
    wait_norms: Iterable[float],
    *,
    sofa_weight: float = 0.6,
    wait_weight: float = 0.4,
    sofa_max: float = SOFA_MAX,
) -> list[float]:
    """Composite priority with normalized SOFA and waiting percentile."""
    sofa = [float(x) for x in sofa_totals]
    waits = [float(x) for x in wait_norms]
    if len(sofa) != len(waits):
        raise ValueError("sofa_totals and wait_norms length mismatch")
    if sofa_weight < 0 or wait_weight < 0:
        raise ValueError("priority weights must be non-negative")
    if sofa_weight + wait_weight <= 0:
        raise ValueError("at least one priority weight must be positive")

    out: list[float] = []
    for s, w in zip(sofa, waits):
        s_norm = min(max(s, 0.0), sofa_max) / sofa_max
        w_norm = min(max(w, 0.0), 1.0)
        out.append(round(1.0 + sofa_weight * s_norm + wait_weight * w_norm, 4))
    return out


def build_priority(
    mode: str,
    sofa_totals: Iterable[float],
    wait_norms: Iterable[float],
    cfg: Mapping[str, object] | None = None,
) -> list[float]:
    """Dispatch priority construction by mode."""
    cfg = cfg or {}
    if mode == "sofa_rule":
        return sofa_rule(sofa_totals)
    if mode == "composite":
        return composite(
            sofa_totals,
            wait_norms,
            sofa_weight=float(cfg.get("sofa_weight", 0.6)),
            wait_weight=float(cfg.get("wait_weight", 0.4)),
        )
    raise ValueError(f"unknown priority.mode: {mode}; expected one of {', '.join(PRIORITY_MODES)}")
