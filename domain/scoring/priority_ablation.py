"""SOFA-only vs GBDT priority ablation (in-repo; no decision risk)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy import text

from domain.scoring.predict_priority import _careunit_code, _fit_gbdt, _load_training_frame
from infra.db import get_engine

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "priority_ablation.json"


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra = a.argsort().argsort().astype(float)
    rb = b.argsort().argsort().astype(float)
    if ra.std() < 1e-12 or rb.std() < 1e-12:
        return float("nan")
    return float(np.corrcoef(ra, rb)[0, 1])


def _topk_overlap(a: np.ndarray, b: np.ndarray, k: int = 50) -> float:
    ia = set(np.argsort(-a)[:k].tolist())
    ib = set(np.argsort(-b)[:k].tolist())
    return float(len(ia & ib) / max(k, 1))


def run_priority_ablation(*, top_k: int = 50) -> dict[str, Any]:
    engine = get_engine()
    with engine.connect() as conn:
        rows = _load_training_frame(conn)
    if len(rows) < 100:
        return {"status": "empty", "n": len(rows)}

    vocab: dict[str, int] = {}
    sofa = np.asarray([float(r["sofa_total"] or 0.0) for r in rows], dtype=float)
    los = np.asarray([float(r["los_hours"] or 0.0) for r in rows], dtype=float)
    cu = np.asarray(
        [_careunit_code(str(r["first_careunit"] or ""), vocab) for r in rows],
        dtype=float,
    )
    # Baselines
    sofa_only = 1.0 + sofa / 10.0
    formula = 1.0 + sofa / 10.0 + 2.0 / (1.0 + np.maximum(los, 1.0))
    X = np.column_stack([sofa, cu, los])
    y = formula
    backend, model = _fit_gbdt(X, y)
    gbdt = np.clip(np.asarray(model.predict(X), dtype=float), 1.0, 5.0)

    payload: dict[str, Any] = {
        "status": "ok",
        "n": len(rows),
        "backend": backend,
        "note": (
            "In-repo priority ablation: SOFA-only vs constructed formula vs GBDT. "
            "Does not read decision risk_score."
        ),
        "correlations": {
            "spearman_sofa_vs_gbdt": _spearman(sofa_only, gbdt),
            "spearman_formula_vs_gbdt": _spearman(formula, gbdt),
        },
        "topk_overlap": {
            "k": int(top_k),
            "sofa_vs_gbdt": _topk_overlap(sofa_only, gbdt, top_k),
            "formula_vs_gbdt": _topk_overlap(formula, gbdt, top_k),
        },
        "means": {
            "sofa_only": float(sofa_only.mean()),
            "formula": float(formula.mean()),
            "gbdt": float(gbdt.mean()),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    payload["artifact"] = str(OUT).replace("\\", "/")
    return payload
