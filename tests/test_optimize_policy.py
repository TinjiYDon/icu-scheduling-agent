from __future__ import annotations

import pytest

from application.optimize import optimize


def test_optimize_rejects_unknown_policy_without_database_access():
    with pytest.raises(ValueError, match="unsupported scheduling policy"):
        optimize(policy="unknown")


def test_hybrid_policy_is_explicitly_reserved():
    with pytest.raises(NotImplementedError, match="hybrid"):
        optimize(policy="hybrid")
