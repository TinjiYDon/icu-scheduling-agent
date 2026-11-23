"""S1: isolation-mode 开关（正常负载敏感性实验用）。"""
from domain.optimizer.constraint_rules import needs_isolation


def test_isolation_config_keywords_default(monkeypatch):
    monkeypatch.delenv("CONSTRAINT_ISOLATION_MODE", raising=False)
    assert needs_isolation("MICU") is True
    assert needs_isolation("Floor") is False


def test_isolation_mode_none(monkeypatch):
    monkeypatch.setenv("CONSTRAINT_ISOLATION_MODE", "none")
    assert needs_isolation("MICU") is False
    assert needs_isolation("SICU") is False
