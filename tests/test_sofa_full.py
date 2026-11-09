from datetime import datetime, timedelta

from domain.scoring.sofa_full import compute_snapshot, score_components

T = datetime(2150, 1, 1)


def event(table, itemid, hour, n=None, **extra):
    unit = "mg/dL" if itemid in {50912, 50885} else "mmHg" if itemid == 50821 else ""
    return dict(
        table=table,
        itemid=itemid,
        charttime=(T + timedelta(hours=hour)).isoformat(),
        storetime=(T + timedelta(hours=hour)).isoformat(),
        valuenum=n,
        **({"valueuom": unit} | extra),
    )


def test_six_components_and_boundaries():
    s = score_components(
        {
            "pf_vent": 99,
            "platelet": 19,
            "bilirubin": 12,
            "dopamine": 16,
            "gcs": 5,
            "creatinine": 5,
        }
    )
    assert list(s.values()) == [4, 4, 4, 4, 4, 4]
    s = score_components(
        {
            "pf_vent": 100,
            "platelet": 20,
            "bilirubin": 6,
            "dopamine": 15,
            "gcs": 6,
            "creatinine": 3.5,
        }
    )
    assert list(s.values()) == [3, 3, 3, 3, 3, 3]
    assert score_components({"pf_novent": 50})["respiration"] == 2
    assert score_components({}) == dict.fromkeys(s, None)


def test_storetime_and_future_observations_are_not_visible():
    rows = [
        event("labevents", 50912, 1, 1.0),
        event("labevents", 50912, 3, 9.0),
        event("labevents", 50912, 1.5, 8.0),
    ]
    rows[2]["storetime"] = (T + timedelta(hours=4)).isoformat()
    snap = compute_snapshot(1, T, 2, rows)
    assert snap["components"]["renal"] == 0
    assert snap["sofa_total"] == 0
    assert "respiration" in snap["missing_components"]
    assert compute_snapshot(1, T, 4, rows)["components"]["renal"] == 4


def test_left_open_window_excludes_expired_measurement():
    rows = [event("labevents", 50912, 0, 9.0), event("labevents", 50912, 1, 1.0)]
    assert compute_snapshot(1, T, 24, rows)["components"]["renal"] == 0


def test_initial_window_includes_exact_icu_admission_with_available_data():
    rows = [event("labevents", 50912, 0, 9.0)]
    snap = compute_snapshot(1, T, 0, rows)
    assert snap["components"]["renal"] == 4
    assert snap["window_left_open"] is False
    assert compute_snapshot(1, T, 24, rows)["window_left_open"] is True


def test_arterial_specimen_and_prior_fio2_required():
    rows = [
        event("labevents", 52033, 1, value="VEN.", specimen_id="a"),
        event("labevents", 50821, 1, 40, specimen_id="a"),
        event("chartevents", 223835, 0.5, 50),
        event("chartevents", 226732, 0.5, value="Endotracheal tube"),
    ]
    assert compute_snapshot(1, T, 2, rows)["components"]["respiration"] is None
    rows[0]["value"] = "ART."
    assert compute_snapshot(1, T, 2, rows)["components"]["respiration"] == 4
    rows[2]["charttime"] = (T + timedelta(hours=1.5)).isoformat()
    assert compute_snapshot(1, T, 2, rows)["components"]["respiration"] is None


def test_gcs_ett_is_not_scored_as_coma():
    rows = [
        event("chartevents", 223900, 1, 1, value="No Response-ETT"),
        event("chartevents", 223901, 1, 1),
        event("chartevents", 220739, 1, 1),
    ]
    snap = compute_snapshot(1, T, 2, rows)
    assert snap["components"]["cns"] == 0
    assert "gcs_ett_default_15" in snap["quality_flags"]


def test_mimic_blood_gas_mm_hg_unit_is_accepted():
    rows = [
        event("labevents", 52033, 1, value="ART.", specimen_id="a"),
        event("labevents", 50821, 1, 80, specimen_id="a", valueuom="mm Hg"),
        event("labevents", 50816, 1, 50, specimen_id="a"),
    ]
    snap = compute_snapshot(1, T, 2, rows)
    assert snap["components"]["respiration"] == 2
    assert "unsupported_po2_unit" not in snap["quality_flags"]


def test_gcs_recovering_from_ett_does_not_carry_sedated_motor_eyes():
    rows = [
        event("chartevents", 223900, 1, 1, value="No Response-ETT"),
        event("chartevents", 223901, 1, 1),
        event("chartevents", 220739, 1, 1),
        event("chartevents", 223900, 2, 5),
    ]
    snap = compute_snapshot(1, T, 3, rows)
    assert snap["inputs"]["gcs"] == 15
    assert snap["components"]["cns"] == 0


def test_drug_uses_recorded_rate_and_not_future_end_time():
    row = event("inputevents", 221906, 1)
    row.update(
        starttime=row["charttime"],
        endtime=(T + timedelta(hours=100)).isoformat(),
        rate=0.2,
        rateuom="mcg/kg/min",
        statusdescription="FinishedRunning",
    )
    assert compute_snapshot(1, T, 2, [row])["components"]["cardiovascular"] == 4
    row["rateuom"] = "mL/hour"
    snap = compute_snapshot(1, T, 2, [row])
    assert snap["components"]["cardiovascular"] is None
    assert "unsupported_vaso_unit" in snap["quality_flags"]


def test_partial_urine_is_not_interpreted_as_24h_oliguria():
    rows = [event("outputevents", 226559, 1, value=10, valueuom="mL")]
    assert compute_snapshot(1, T, 2, rows)["components"]["renal"] is None
    rows = [
        event("outputevents", 226559, h, value=10, valueuom="mL") for h in range(1, 25)
    ]
    assert compute_snapshot(1, T, 24, rows)["components"]["renal"] == 3


def test_missing_storetime_is_flagged_and_excluded():
    row = event("labevents", 50912, 1, 8)
    row.pop("storetime")
    snap = compute_snapshot(1, T, 2, [row])
    assert snap["components"]["renal"] is None
    assert "missing_storetime_excluded" in snap["quality_flags"]
