"""Flywheel archive unit test."""

from __future__ import annotations

from domain.ops.flywheel_archive import archive_flywheel


def test_archive_flywheel(tmp_path, monkeypatch):
    monkeypatch.setattr("domain.ops.flywheel_archive.FLYWHEEL_DIR", tmp_path)
    paths = archive_flywheel("simulate", {"status": "simulate_ok", "n_beds": 20})
    assert (tmp_path / "simulate_latest.json").is_file()
    assert "simulate_" in paths["stamped"]
