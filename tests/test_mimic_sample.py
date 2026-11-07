import csv
import gzip
import io
import json
import zipfile

import pytest

from application.prepare_sofa_sample import score_cache
from data_access.mimic_sample import (
    TABLE_COLUMNS,
    extract_sample,
    load_cached_events,
    select_stays,
)


def stays():
    return [
        {
            "stay_id": str(i),
            "subject_id": str(i),
            "hadm_id": str(i),
            "intime": "2150-01-01 00:00:00",
            "outtime": "2150-01-04 00:00:00",
            "first_careunit": "MICU",
        }
        for i in range(1, 6)
    ]


def test_selection_is_reproducible_independent_of_input_order():
    assert select_stays(stays(), 2, 42) == select_stays(list(reversed(stays())), 2, 42)
    assert select_stays(stays(), 2, 42) != select_stays(stays(), 2, 43)
    short = dict(stays()[0], outtime="2150-01-01 05:00:00")
    with pytest.raises(ValueError):
        select_stays([short], 1, 42)


def write_member(z, table, rows, fields):
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    folder = "hosp" if table == "labevents" else "icu"
    z.writestr(
        f"mimic-iv-3.1/{folder}/{table}.csv.gz", gzip.compress(buf.getvalue().encode())
    )


def test_zip_stream_cache_and_asof_roundtrip(tmp_path):
    archive = tmp_path / "mini.zip"
    with zipfile.ZipFile(archive, "w") as z:
        write_member(z, "icustays", stays(), list(stays()[0]))
        for table, cols in TABLE_COLUMNS.items():
            rows = []
            if table == "labevents":
                for s in stays():
                    rows += [
                        {
                            "subject_id": s["subject_id"],
                            "hadm_id": s["hadm_id"],
                            "specimen_id": s["stay_id"],
                            "itemid": "50912",
                            "charttime": "2150-01-01 01:00:00",
                            "storetime": "2150-01-01 03:00:00",
                            "value": "2.5",
                            "valuenum": "2.5",
                            "valueuom": "mg/dL",
                        }
                    ]
            write_member(z, table, rows, cols)
    cache = tmp_path / "cache"
    manifest = extract_sample(archive, cache, size=2, chunksize=2)
    assert len(manifest["stays"]) == 2
    raw = load_cached_events(cache)
    assert set(raw) == {s["stay_id"] for s in manifest["stays"]}
    assert all(len(v) == 1 for v in raw.values())
    again = extract_sample(archive, cache, size=2, chunksize=1)
    assert again["identity"] == manifest["identity"]
    assert again["scan_counts"] == manifest["scan_counts"]
    assert set(again["scan_counts"]) == set(TABLE_COLUMNS)
    with pytest.raises(ValueError, match="cache belongs"):
        extract_sample(archive, cache, size=3)
    report = score_cache(cache, tmp_path / "scores.json", hours=4)
    sid = manifest["stays"][0]["stay_id"]
    scores = {r["hour_index"]: r for r in report["scores"] if r["stay_id"] == sid}
    assert scores[2]["components"]["renal"] is None
    assert scores[4]["components"]["renal"] == 2
    assert (
        json.loads((tmp_path / "scores.json").read_text())["coverage"]["n_scores"] == 6
    )
