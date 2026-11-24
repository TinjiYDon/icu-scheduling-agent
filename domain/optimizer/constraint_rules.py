"""Configurable isolation / ventilator demand rules (S0–S1)."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from typing import Any

from infra.config import load_yaml


@lru_cache(maxsize=1)
def load_constraint_rules() -> dict[str, Any]:
    try:
        return load_yaml("constraint_rules.yaml")
    except Exception:
        return {
            "isolation": {"mode": "careunit_keywords", "keywords": ["micu", "sicu", "cvicu", "nsicu"]},
            "ventilator": {"mode": "stay_hash_pct", "hash_pct": 35},
            "disclosure": "default heuristic rules",
        }


def needs_isolation(careunit: str | None) -> bool:
    cfg = load_constraint_rules().get("isolation", {})
    mode = str(cfg.get("mode", "careunit_keywords"))
    if mode == "none":
        return False
    keywords = [str(k).lower() for k in cfg.get("keywords", [])]
    cu = (careunit or "").lower()
    return any(kw in cu for kw in keywords)


def needs_ventilator(stay_id: int, sofa_total: float = 0.0) -> bool:
    """Mark ventilator demand (deterministic per stay_id).

    Modes (configs/constraint_rules.yaml → ventilator.mode):
      sofa_weighted — SOFA-driven probability curve (data-driven):
                      SOFA>=high → ``sofa_high_pct`` (e.g. 90%),
                      SOFA>=mid  → ``sofa_mid_pct``,
                      else       → ``sofa_low_pct``.
      stay_hash_pct — flat deterministic hash percentage (``hash_pct``).
      none          — disabled.
    """
    cfg = load_constraint_rules().get("ventilator", {})
    mode = str(cfg.get("mode", "sofa_weighted"))
    if mode == "none":
        return False
    h = hashlib.md5(str(int(stay_id)).encode()).hexdigest()
    bucket = int(h[:8], 16) % 100
    if mode == "sofa_weighted":
        hi_thr = float(cfg.get("sofa_high_threshold", 10))
        mid_thr = float(cfg.get("sofa_mid_threshold", 6))
        sofa = float(sofa_total or 0.0)
        if sofa >= hi_thr:
            pct = float(cfg.get("sofa_high_pct", 90))
        elif sofa >= mid_thr:
            pct = float(cfg.get("sofa_mid_pct", 55))
        else:
            pct = float(cfg.get("sofa_low_pct", 20))
    else:  # stay_hash_pct
        pct = float(cfg.get("hash_pct", 35))
    return bucket < max(0.0, min(100.0, pct))


def constraint_disclosure() -> dict[str, Any]:
    cfg = load_constraint_rules()
    vent = cfg.get("ventilator") or {}
    return {
        "isolation_mode": (cfg.get("isolation") or {}).get("mode"),
        "ventilator_mode": vent.get("mode"),
        "ventilator_hash_pct": vent.get("hash_pct"),
        "ventilator_sofa_curve": {
            "high_threshold": vent.get("sofa_high_threshold"),
            "mid_threshold": vent.get("sofa_mid_threshold"),
            "high_pct": vent.get("sofa_high_pct"),
            "mid_pct": vent.get("sofa_mid_pct"),
            "low_pct": vent.get("sofa_low_pct"),
        },
        "disclosure": cfg.get("disclosure", ""),
    }
