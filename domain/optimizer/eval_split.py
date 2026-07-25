"""Calib / eval stay split for scheduling (NOT train/val/test)."""

from __future__ import annotations

from typing import Any

import numpy as np

from infra.config import load_yaml


def load_eval_config() -> dict[str, Any]:
    opt = load_yaml("optimizer.yaml")
    ev = opt.get("eval_split", {})
    return {
        "calib_ratio": float(ev.get("calib_ratio", 0.7)),
        "seed": int(ev.get("seed", 42)),
    }


def split_stay_ids(stay_ids: list[int], *, calib_ratio: float | None = None, seed: int | None = None) -> dict[str, Any]:
    """Split stay ids into calib (tune) vs eval (report-only)."""
    cfg = load_eval_config()
    calib_ratio = cfg["calib_ratio"] if calib_ratio is None else calib_ratio
    seed = cfg["seed"] if seed is None else seed
    ids = sorted({int(s) for s in stay_ids})
    rng = np.random.default_rng(seed)
    perm = list(ids)
    rng.shuffle(perm)
    n_calib = int(round(len(perm) * calib_ratio))
    if len(perm) > 0 and n_calib >= len(perm):
        n_calib = max(0, len(perm) - 1)
    calib = perm[:n_calib]
    eval_ids = perm[n_calib:]
    return {
        "seed": seed,
        "calib_ratio": calib_ratio,
        "calib_stay_ids": calib,
        "eval_stay_ids": eval_ids,
        "n_calib": len(calib),
        "n_eval": len(eval_ids),
    }
