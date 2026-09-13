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


def needs_ventilator(stay_id: int) -> bool:
    cfg = load_constraint_rules().get("ventilator", {})
    mode = str(cfg.get("mode", "stay_hash_pct"))
    if mode == "none":
        return False
    pct = int(cfg.get("hash_pct", 35))
    h = hashlib.md5(str(int(stay_id)).encode()).hexdigest()
    return int(h[:8], 16) % 100 < max(0, min(100, pct))


def constraint_disclosure() -> dict[str, Any]:
    cfg = load_constraint_rules()
    return {
        "isolation_mode": (cfg.get("isolation") or {}).get("mode"),
        "ventilator_mode": (cfg.get("ventilator") or {}).get("mode"),
        "ventilator_hash_pct": (cfg.get("ventilator") or {}).get("hash_pct"),
        "disclosure": cfg.get("disclosure", ""),
    }
