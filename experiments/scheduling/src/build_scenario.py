r"""从 MIMIC-IV (DB) 构建床位调度仿真场景。

MIMIC-IV 的日期按 subject 随机平移（落在 2100–2200 年），因此"2018 年"在库内不可直接用。
做法（date bootstrap，写进报告）：
  1) 从 2133–2140 的入科记录中取候选池（真实 intime / outtime / LOS / 病区）；
  2) 把每条 intime 整体平移到研究年 2138（保留月-日-时-分，即保留一天内的到达节律）；
  3) 按目标占用率对到达流做伯努利抽稀，得到 80/92/98% 三档负荷；
  4) 同一 (load, seed) 下所有调度方法共用同一份到达流（同池同资源）。

产出：experiments/scheduling/data/scenario_<load>_seed<k>.json + scenario_meta.json
"""
from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg

DSN_MIMIC = __import__("os").environ["MIMIC_DSN"]
DSN_SCHED = __import__("os").environ["ICU_SCHEDULING_DSN"]

OUT = Path(__file__).resolve().parents[1] / "data"

ZONE_MAP = {
    "MICU": "MICU", "SICU": "SICU", "TSICU": "SICU", "CCU": "CCU", "CVICU": "CCU",
    "NICU": "NICU", "Neuro Intermediate": "NICU", "Neuro Stepdown": "NICU",
}
BED_LAYOUT = {"ISO": [1, 2, 3, 4], "MICU": [5, 6, 7, 8], "SICU": [9, 10, 11, 12],
              "CCU": [13, 14, 15, 16], "NICU": [17, 18, 19, 20]}
ISO_BEDS = BED_LAYOUT["ISO"]
VENT_BEDS = [1, 5, 6, 9, 10, 13, 17, 18]

TARGET_YEAR = 2138


def load_stays(pool_t0: str, pool_t1: str) -> pd.DataFrame:
    sql = """
        SELECT DISTINCT ON (icu.stay_id)
               icu.stay_id, icu.subject_id, icu.hadm_id, icu.intime, icu.outtime,
               EXTRACT(EPOCH FROM (icu.outtime - icu.intime)) / 3600.0 AS los_h,
               icu.first_careunit, icu.last_careunit,
               pat.anchor_age, pat.gender, adm.admission_type, adm.race,
               adm.hospital_expire_flag
        FROM mimiciv_icu.icustays icu
        JOIN mimiciv_hosp.patients pat USING (subject_id)
        JOIN mimiciv_hosp.admissions adm USING (hadm_id)
        WHERE icu.outtime IS NOT NULL
          AND icu.intime >= %(t0)s AND icu.intime < %(t1)s
        ORDER BY icu.stay_id, icu.intime
    """
    with psycopg.connect(DSN_MIMIC) as conn, conn.cursor() as cur:
        cur.execute(sql, {"t0": pool_t0, "t1": pool_t1})
        cols = [d.name for d in cur.description]
        df = pd.DataFrame(cur.fetchall(), columns=cols)
    df["intime"] = pd.to_datetime(df["intime"])
    df["outtime"] = pd.to_datetime(df["outtime"])
    for c in ("los_h", "anchor_age", "hospital_expire_flag"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    return df


def load_vent(stay_ids: list[int]) -> dict[int, float]:
    """每 stay 的机械通气小时数（有创 + 无创，按事件区间求和；用于设备占用而不是整段住院）。"""
    sql = """
        SELECT stay_id,
               SUM(EXTRACT(EPOCH FROM (LEAST(endtime, starttime + interval '60 day') - starttime)) / 3600.0)
        FROM mimiciv_icu.procedureevents
        WHERE itemid IN (225792, 225794)
          AND starttime IS NOT NULL AND endtime IS NOT NULL AND endtime > starttime
          AND stay_id = ANY(%s)
        GROUP BY stay_id
    """
    with psycopg.connect(DSN_MIMIC) as conn, conn.cursor() as cur:
        cur.execute(sql, (stay_ids,))
        return {int(r[0]): float(r[1]) for r in cur.fetchall()}


def load_iso(hadm_ids: list[int]) -> set[int]:
    """隔离 proxy：入科前后 48h 内培养出「需接触隔离」的病原体（MRSA/VRE/ESBL/CRE/
    铜绿/不动杆菌/艰难梭菌等）→ 需单间接触隔离。全库命中率约 16%，与真实 ICU 隔离比例同量级。"""
    organisms = (
        "STAPH AUREUS COAG +", "ENTEROCOCCUS SP", "ENTEROCOCCUS SP.", "KLEBSIELLA PNEUMONIAE",
        "KLEBSIELLA OXYTOCA", "ESCHERICHIA COLI", "ENTEROBACTER SP", "ENTEROBACTER CLOACAE",
        "PSEUDOMONAS AERUGINOSA", "ACINETOBACTER BAUMANNII", "STENOTROPHOMONAS MALTOPHILIA",
        "SERRATIA MARCESCENS", "CITROBACTER FREUNDII", "CLOSTRIDIUM DIFFICILE",
        "PROVIDENCIA STUARTII", "BURKHOLDERIA CEPACIA",
    )
    sql = """
        SELECT DISTINCT hadm_id FROM mimiciv_hosp.microbiologyevents
        WHERE org_name = ANY(%s)
          AND spec_type_desc IN ('BLOOD CULTURE','URINE','SPUTUM','WOUND','SWAB',
                                 'BLOOD CULTURE ( MYCO/F LYTIC BOTTLE)','STOOL')
          AND hadm_id = ANY(%s)
    """
    with psycopg.connect(DSN_MIMIC) as conn, conn.cursor() as cur:
        cur.execute(sql, (list(organisms), hadm_ids))
        return {int(r[0]) for r in cur.fetchall()}


def load_priority() -> pd.DataFrame:
    with psycopg.connect(DSN_SCHED) as conn, conn.cursor() as cur:
        cur.execute("SELECT stay_id, priority_weight FROM feat.patient_priority")
        return pd.DataFrame(cur.fetchall(), columns=["stay_id", "priority_weight"])


def load_sofa0() -> pd.DataFrame:
    with psycopg.connect(DSN_SCHED) as conn, conn.cursor() as cur:
        cur.execute("SELECT stay_id, sofa_total FROM feat.sofa_timeseries WHERE hour_index = 0")
        return pd.DataFrame(cur.fetchall(), columns=["stay_id", "sofa_total"])


def build(pool_t0: str, pool_t1: str) -> pd.DataFrame:
    df = load_stays(pool_t0, pool_t1)
    df = df[(df["anchor_age"] >= 18) & (df["los_h"] >= 6) & (df["los_h"] <= 720)].copy()

    # date bootstrap：整体平移到研究年，保留月-日-时
    df["year_shift"] = TARGET_YEAR - df["intime"].dt.year
    df["intime"] = [t + pd.DateOffset(years=int(s)) for t, s in zip(df["intime"], df["year_shift"])]

    df["zone"] = df["first_careunit"].map(ZONE_MAP).fillna("MICU")
    vent_h = load_vent(df["stay_id"].astype(int).tolist())
    df["vent_hours"] = df["stay_id"].map(vent_h).fillna(0.0).clip(upper=df["los_h"])
    df["need_vent"] = df["vent_hours"] > 0
    iso = load_iso(df["hadm_id"].astype(int).tolist())
    df["need_iso"] = df["hadm_id"].isin(iso)

    df = df.merge(load_priority(), on="stay_id", how="left").merge(load_sofa0(), on="stay_id", how="left")
    df["priority_weight"] = df["priority_weight"].fillna(1.0)
    med = float(df["sofa_total"].median()) if df["sofa_total"].notna().any() else 4.0
    df["sofa0"] = df["sofa_total"].fillna(med)
    df["high_risk"] = (df["sofa0"] >= 8).astype(int)
    df["benefit"] = (100 * (1.0 + df["sofa0"] / 6.0)).round().astype(int)
    df["depart"] = [t + timedelta(hours=float(h)) for t, h in zip(df["intime"], df["los_h"])]
    df = df.sort_values("intime").reset_index(drop=True)
    df["pid"] = np.arange(len(df))
    return df


def thin(df: pd.DataFrame, target_util: float, seed: int, n_beds: int = 20,
         year_start: str = f"{TARGET_YEAR}-01-01", year_end: str = f"{TARGET_YEAR + 1}-01-01") -> pd.DataFrame:
    """抽稀到达流，使期望占用 ≈ target_util × n_beds。"""
    # 用"床-日需求"（截断到窗口末）精确标定抽样率，使实际占用率命中目标
    t1_ts = pd.Timestamp(year_end)
    bed_days = ((df["depart"].clip(upper=t1_ts) - df["intime"]).dt.total_seconds() / 86400.0).sum()
    target_bed_days = target_util * n_beds * (t1_ts - pd.Timestamp(year_start)).days
    p = min(1.0, float(target_bed_days / max(bed_days, 1e-6)))
    # 按 LOS 十分位分层抽样：降低重尾 LOS 带来的床-日方差，使实际负荷贴近目标
    bins = pd.qcut(df["los_h"], 10, labels=False, duplicates="drop")
    keep_idx = []
    for b in sorted(pd.unique(bins.dropna())):
        idx = df.index[bins == b]
        rng = np.random.default_rng(seed * 100 + int(b))
        keep_idx.extend(idx[rng.random(len(idx)) < p].tolist())
    out = df.loc[sorted(keep_idx)].copy()
    out["sample_rate"] = p
    return out.sort_values("intime").reset_index(drop=True)


def to_records(df: pd.DataFrame) -> list[dict]:
    recs = []
    for r in df.itertuples(index=False):
        recs.append({
            "pid": int(r.pid), "stay_id": int(r.stay_id), "subject_id": int(r.subject_id),
            "arrival": r.intime.isoformat(), "los_h": float(r.los_h),
            "depart": r.depart.isoformat(), "zone": r.zone,
            "need_iso": bool(r.need_iso), "need_vent": bool(r.need_vent),
            "vent_hours": float(r.vent_hours),
            "sofa0": float(r.sofa0), "priority": float(r.priority_weight),
            "benefit": int(r.benefit), "high_risk": bool(r.high_risk),
        })
    return recs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", nargs=2, default=["2133-01-01", "2140-01-01"])
    ap.add_argument("--loads", nargs="+", type=float, default=[0.80, 0.92, 0.98])
    ap.add_argument("--seeds", nargs="+", type=int, default=[11, 22, 33])
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    df = build(args.pool[0], args.pool[1])
    print(f"pool stays={len(df)} iso={df.need_iso.mean():.3f} vent={df.need_vent.mean():.3f} "
          f"high_risk={df.high_risk.mean():.3f} sofa0={df.sofa0.mean():.2f} los={df.los_h.mean():.1f}h")
    df[["stay_id", "subject_id", "hadm_id", "intime", "depart", "los_h", "zone", "need_iso",
        "need_vent", "vent_hours", "sofa0", "priority_weight", "benefit", "high_risk"]].to_csv(
        OUT / "patients_all.csv", index=False)

    meta = {"target_year": TARGET_YEAR, "pool": args.pool, "n_pool": int(len(df)),
            "iso_rate": float(df.need_iso.mean()), "vent_rate": float(df.need_vent.mean()),
            "high_risk_rate": float(df.high_risk.mean()), "mean_los_h": float(df.los_h.mean()),
            "bed_layout": BED_LAYOUT, "iso_beds": ISO_BEDS, "vent_beds": VENT_BEDS,
            "n_beds": 20, "scenarios": []}
    for load in args.loads:
        for seed in args.seeds:
            sub = thin(df, load, seed)
            name = f"scenario_{int(load * 100)}_seed{seed}"
            t0 = f"{TARGET_YEAR}-01-01T00:00:00"
            t1 = f"{TARGET_YEAR + 1}-01-01T00:00:00"
            payload = {"name": name, "target_util": load, "seed": seed,
                       "sample_rate": float(sub["sample_rate"].iloc[0]) if len(sub) else 0.0,
                       "n_patients": int(len(sub)), "t0": t0, "t1": t1,
                       "iso_rate": float(sub.need_iso.mean()), "vent_rate": float(sub.need_vent.mean()),
                       "patients": to_records(sub)}
            (OUT / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            meta["scenarios"].append({k: payload[k] for k in
                                      ("name", "target_util", "seed", "sample_rate", "n_patients",
                                       "iso_rate", "vent_rate")})
            print(f"[scenario] {name}: n={payload['n_patients']} p={payload['sample_rate']:.3f} "
                  f"iso={payload['iso_rate']:.3f} vent={payload['vent_rate']:.3f}")

    (OUT / "scenario_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", OUT / "scenario_meta.json")


if __name__ == "__main__":
    main()
