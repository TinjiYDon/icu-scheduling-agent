"""ETL smoke test — slow: rewrites staging.icustays from the read source."""

from __future__ import annotations

import pytest


@pytest.mark.slow
def test_etl_smoke():
    from application.etl_pipeline import run_etl
    from data_access.mimic_repo import layer0_available
    from infra.config import get_data_source

    if not layer0_available():
        pytest.skip("Layer0 icustays unavailable; import MIMIC or set source: mock")

    r = run_etl()
    expected = "mock_ok" if get_data_source() == "mock" else "mimic_ok"
    assert r["status"] == expected
    assert r["staging_icustays"] >= 1
    assert r["icustays"] == r["staging_icustays"]


def test_config_phase():
    from infra.config import get_data_phase

    assert get_data_phase() == "P0"
