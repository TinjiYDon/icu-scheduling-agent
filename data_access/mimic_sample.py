"""Deterministic small-cohort extraction from a local MIMIC-IV ZIP.

Only selected SOFA item IDs are retained. Huge tables are streamed once and
cached separately from scoring. No database or full decompressed table needed.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import random
import zipfile
from datetime import timedelta
from pathlib import Path

import pandas as pd

from domain.scoring.sofa_full import (
    CHART_ITEMS,
    LAB_ITEMS,
    URINE_ITEMS,
    VASO_ITEMS,
    timestamp,
)

TABLE_ITEMS = {
    "labevents": LAB_ITEMS,
    "chartevents": CHART_ITEMS,
    "inputevents": set(VASO_ITEMS),
    "outputevents": URINE_ITEMS,
}
TABLE_COLUMNS = {
    "labevents": [
        "subject_id",
        "hadm_id",
        "specimen_id",
        "itemid",
        "charttime",
        "storetime",
        "value",
        "valuenum",
        "valueuom",
    ],
    "chartevents": [
        "subject_id",
        "hadm_id",
        "stay_id",
        "itemid",
        "charttime",
        "storetime",
        "value",
        "valuenum",
        "valueuom",
    ],
    "inputevents": [
        "subject_id",
        "hadm_id",
        "stay_id",
        "itemid",
        "starttime",
        "endtime",
        "storetime",
        "rate",
        "rateuom",
        "patientweight",
        "statusdescription",
    ],
    "outputevents": [
        "subject_id",
        "hadm_id",
        "stay_id",
        "itemid",
        "charttime",
        "storetime",
        "value",
        "valueuom",
    ],
}


def member_path(z: zipfile.ZipFile, suffix: str) -> str:
    found = [n for n in z.namelist() if n.endswith("/" + suffix)]
    if len(found) != 1:
        raise ValueError(
            f"expected one ZIP member ending in {suffix}, found {len(found)}"
        )
    return found[0]


def _write_manifest(path: Path, manifest: dict) -> None:
    temp = path.with_suffix(".json.part")
    temp.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temp.replace(path)


def select_stays(
    rows: list[dict], size: int, seed: int, min_stay_hours: int = 48
) -> list[dict]:
    eligible = []
    for row in rows:
        t0, t1 = timestamp(row.get("intime")), timestamp(row.get("outtime"))
        if t0 and t1 and t1 - t0 >= timedelta(hours=min_stay_hours):
            eligible.append(row)
    eligible.sort(key=lambda r: int(r["stay_id"]))
    if size < 1 or size > len(eligible):
        raise ValueError(
            f"sample size {size} exceeds eligible stays {len(eligible)} or is invalid"
        )
    selected = random.Random(seed).sample(eligible, size)
    return [
        dict(r, **{k: int(r[k]) for k in ("stay_id", "subject_id", "hadm_id")})
        for r in sorted(selected, key=lambda r: int(r["stay_id"]))
    ]


def extract_sample(
    zip_path: str | Path,
    cache_dir: str | Path,
    *,
    size: int = 50,
    seed: int = 42,
    min_stay_hours: int = 48,
    max_hours: int = 48,
    chunksize: int = 500_000,
) -> dict:
    """Sequentially scan ZIP gzip members; every completed table is reusable.

    Cache identity includes archive size/mtime, member CRCs, sampling, retained
    items and schema. Interrupted table writes are atomic and never reused.
    """
    archive, root = Path(zip_path).resolve(), Path(cache_dir)
    root.mkdir(parents=True, exist_ok=True)
    config = {
        "schema_version": 1,
        "archive": str(archive),
        "archive_bytes": archive.stat().st_size,
        "archive_mtime_ns": archive.stat().st_mtime_ns,
        "size": size,
        "seed": seed,
        "min_stay_hours": min_stay_hours,
        "max_hours": max_hours,
        "itemids": {k: sorted(v) for k, v in TABLE_ITEMS.items()},
    }
    with zipfile.ZipFile(archive) as z:
        members = {
            t: member_path(z, ("hosp/" if t == "labevents" else "icu/") + t + ".csv.gz")
            for t in TABLE_ITEMS
        }
        config["member_crc"] = {k: z.getinfo(v).CRC for k, v in members.items()}
        identity = hashlib.sha256(
            json.dumps(config, sort_keys=True).encode()
        ).hexdigest()
        manifest_path = root / "manifest.json"
        old = {}
        if manifest_path.exists():
            old = json.loads(manifest_path.read_text(encoding="utf-8"))
            if old["identity"] != identity:
                raise ValueError(
                    "cache belongs to different archive/sample/config; use another --cache directory"
                )
        with (
            z.open(member_path(z, "icu/icustays.csv.gz")) as f,
            gzip.GzipFile(fileobj=f) as gz,
        ):
            stays = select_stays(
                list(csv.DictReader(io.TextIOWrapper(gz))), size, seed, min_stay_hours
            )
        counts = dict(old.get("scan_counts", {}))
        manifest = {
            "identity": identity,
            "config": config,
            "stays": stays,
            "scan_counts": counts,
        }
        _write_manifest(manifest_path, manifest)
        stay_ids = {str(r["stay_id"]) for r in stays}
        subjects = {str(r["subject_id"]) for r in stays}
        by_subject = {}
        for s in stays:
            by_subject.setdefault(str(s["subject_id"]), []).append(s)
        for table, member in members.items():
            target = root / f"{table}.jsonl"
            if target.exists():
                print(f"{table}: cached {target}", flush=True)
                continue
            temp = target.with_suffix(".jsonl.part")
            scanned = kept = 0
            with (
                z.open(member) as source,
                gzip.GzipFile(fileobj=source) as gz,
                temp.open("w", encoding="utf-8") as out,
            ):
                chunks = pd.read_csv(
                    gz,
                    usecols=TABLE_COLUMNS[table],
                    dtype=str,
                    keep_default_na=False,
                    chunksize=chunksize,
                )
                for chunk in chunks:
                    scanned += len(chunk)
                    key, ids = (
                        ("subject_id", subjects)
                        if table == "labevents"
                        else ("stay_id", stay_ids)
                    )
                    selected = chunk[
                        chunk[key].isin(ids)
                        & chunk["itemid"].isin({str(i) for i in TABLE_ITEMS[table]})
                    ]
                    for row in selected.to_dict("records"):
                        candidates = (
                            by_subject.get(row["subject_id"], [])
                            if table == "labevents"
                            else [
                                s for s in stays if str(s["stay_id"]) == row["stay_id"]
                            ]
                        )
                        event_time = timestamp(
                            row.get("charttime", row.get("starttime"))
                        )
                        for s in candidates:
                            if row["hadm_id"] and row["hadm_id"] != str(s["hadm_id"]):
                                continue
                            t0 = timestamp(s["intime"])
                            t1 = min(
                                timestamp(s["outtime"]), t0 + timedelta(hours=max_hours)
                            )
                            if event_time and t0 <= event_time <= t1:
                                row_out = dict(row, table=table, stay_id=s["stay_id"])
                                out.write(
                                    json.dumps(row_out, ensure_ascii=False) + "\n"
                                )
                                kept += 1
                    print(f"{table}: scanned={scanned:,} kept={kept:,}", flush=True)
            temp.replace(target)
            counts[table] = {"scanned": scanned, "kept": kept}
            _write_manifest(manifest_path, manifest)
        manifest["scan_counts"] = counts
        _write_manifest(manifest_path, manifest)
        return manifest


def load_cached_events(cache_dir: str | Path) -> dict[int, list[dict]]:
    result = {}
    for table in TABLE_ITEMS:
        with (Path(cache_dir) / f"{table}.jsonl").open(encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                result.setdefault(int(row["stay_id"]), []).append(row)
    return result
