"""Backend selection must not conceal training/data errors."""

import sys
from types import SimpleNamespace

import numpy as np
import pytest

from domain.scoring.predict_priority import _fit_gbdt


def test_missing_lightgbm_uses_declared_sklearn_backend(monkeypatch):
    monkeypatch.setitem(sys.modules, "lightgbm", None)
    x = np.arange(12, dtype=float).reshape(-1, 1)
    backend, model = _fit_gbdt(x, x.ravel())
    assert backend == "sklearn_gbr"
    assert np.isfinite(model.predict(x)).all()


def test_training_error_is_propagated_instead_of_switching_backends(monkeypatch):
    class BrokenRegressor:
        def __init__(self, **kwargs):
            pass

        def fit(self, x, y):
            raise ValueError("invalid training data")

    monkeypatch.setitem(sys.modules, "lightgbm", SimpleNamespace(LGBMRegressor=BrokenRegressor))
    with pytest.raises(ValueError, match="invalid training data"):
        _fit_gbdt(np.zeros((2, 1)), np.zeros(2))
