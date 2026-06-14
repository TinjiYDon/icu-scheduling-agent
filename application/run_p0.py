"""P0 end-to-end: ETL → SOFA → CP-SAT."""

from __future__ import annotations

from application.etl_pipeline import run_etl
from application.simulate import run_simulate


def run_p0() -> dict:
    meta = {"steps": []}
    etl = run_etl()
    meta["steps"].append("etl")
    meta["etl"] = etl
    sim = run_simulate()
    meta["steps"].append("simulate")
    meta["simulate"] = sim
    meta["status"] = "p0_ok"
    return meta


if __name__ == "__main__":
    import json

    print(json.dumps(run_p0(), indent=2, ensure_ascii=False))
