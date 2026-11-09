"""Causal, six-component SOFA snapshots from a small raw MIMIC event cohort.

Thresholds follow MIT-LCP SOFA; temporal extraction is a conservative adaptation,
not an exact reproduction of their retrospective hourly SQL. See SOFA_SCORING.md.
"""

from __future__ import annotations

import itertools
import math
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

COMPONENTS = ("respiration", "coagulation", "liver", "cardiovascular", "cns", "renal")
LAB_ITEMS = {50912, 52546, 50885, 53089, 51265, 53189, 50821, 50816, 52033}
MAP_ITEMS = {220052, 220181, 225312}
GCS_ITEMS = {223900, 223901, 220739}
CHART_ITEMS = MAP_ITEMS | GCS_ITEMS | {223835, 226732, 223849, 229314}
VASO_ITEMS = {
    221662: "dopamine",
    221653: "dobutamine",
    221289: "epinephrine",
    221906: "norepinephrine",
}
URINE_ITEMS = {
    226559,
    226560,
    226561,
    226584,
    226563,
    226564,
    226565,
    226567,
    226557,
    226558,
    227488,
    227489,
}
INVASIVE_MODES = {
    "(S) CMV",
    "APRV",
    "APRV/Biphasic+ApnPress",
    "APRV/Biphasic+ApnVol",
    "APV (cmv)",
    "Ambient",
    "Apnea Ventilation",
    "CMV",
    "CMV/ASSIST",
    "CMV/ASSIST/AutoFlow",
    "CMV/AutoFlow",
    "CPAP/PPS",
    "CPAP/PSV",
    "CPAP/PSV+Apn TCPL",
    "CPAP/PSV+ApnPres",
    "CPAP/PSV+ApnVol",
    "MMV",
    "MMV/AutoFlow",
    "MMV/PSV",
    "MMV/PSV/AutoFlow",
    "P-CMV",
    "PCV+",
    "PCV+/PSV",
    "PCV+Assist",
    "PRES/AC",
    "PRVC/AC",
    "PRVC/SIMV",
    "PSV/SBT",
    "SIMV",
    "SIMV/AutoFlow",
    "SIMV/PRES",
    "SIMV/PSV",
    "SIMV/PSV/AutoFlow",
    "SIMV/VOL",
    "SYNCHRON MASTER",
    "SYNCHRON SLAVE",
    "VOL/AC",
    "APV (simv)",
    "P-SIMV",
    "VS",
    "ASV",
}


def number(v: Any) -> float | None:
    try:
        value = float(v)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def timestamp(v: Any) -> datetime | None:
    if isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v))
    except (ValueError, TypeError):
        return None


def score_components(v: dict[str, Any]) -> dict[str, int | None]:
    """Score normalized measurements; absent components remain None, never normal."""

    def high(name, thresholds):
        value = v.get(name)
        return None if value is None else sum(value >= t for t in thresholds)

    def low(name, thresholds):
        value = v.get(name)
        return None if value is None else sum(value < t for t in thresholds)

    pfv, pfn = v.get("pf_vent"), v.get("pf_novent")
    resp = []
    if pfv is not None:
        resp.append(sum(pfv < t for t in (400, 300, 200, 100)))
    if pfn is not None:
        resp.append(sum(pfn < t for t in (400, 300)))
    cardio = []
    if v.get("map") is not None:
        cardio.append(int(v["map"] < 70))
    for name in ("dopamine", "dobutamine", "epinephrine", "norepinephrine"):
        dose = v.get(name)
        if dose is None:
            continue
        if dose <= 0:
            cardio.append(0)
        elif name == "dobutamine":
            cardio.append(2)
        elif name == "dopamine":
            cardio.append(4 if dose > 15 else 3 if dose > 5 else 2)
        else:
            cardio.append(4 if dose > 0.1 else 3)
    renal = high("creatinine", (1.2, 2, 3.5, 5))
    if v.get("urine_24h") is not None:
        u = v["urine_24h"]
        renal = max(renal or 0, 4 if u < 200 else 3 if u < 500 else 0)
    g = v.get("gcs")
    return dict(
        zip(
            COMPONENTS,
            (
                max(resp) if resp else None,
                low("platelet", (150, 100, 50, 20)),
                high("bilirubin", (1.2, 2, 6, 12)),
                max(cardio) if cardio else None,
                None
                if g is None
                else 4
                if g < 6
                else 3
                if g < 10
                else 2
                if g < 13
                else 1
                if g < 15
                else 0,
                renal,
            ),
        )
    )


def _fio2(v):
    n = number(v)
    if n is not None and 0.2 <= n <= 1:
        return n
    if n is not None and 20 <= n <= 100:
        return n / 100
    return None


def compute_snapshot(
    stay_id: int,
    intime: datetime | str,
    hour_index: int,
    events: list[dict],
    window_hours: int = 24,
) -> dict:
    """Use only events charted AND stored by t; window is (t-24h,t].

    Infusions contribute only their already-started recorded rates, not future
    endtime/duration. Availability of rates remains limited by storetime.
    """
    start = timestamp(intime)
    if start is None or hour_index < 0 or window_hours != 24:
        raise ValueError("valid intime, nonnegative hour and a 24h window required")
    end = start + timedelta(hours=hour_index)
    left = end - timedelta(hours=24)
    flags = set()
    visible = []
    # Six hours of look-back context is needed to pair GCS/FiO2/vent evidence.
    for raw in events:
        r = dict(raw)
        t = timestamp(
            r.get("starttime")
            if r.get("table") == "inputevents"
            else r.get("charttime")
        )
        if t is None or t > end or t < start or t <= left - timedelta(hours=6):
            continue
        stored = timestamp(r.get("storetime"))
        if stored is None:
            flags.add("missing_storetime_excluded")
            continue
        if stored > end:
            continue
        r["_t"], r["_s"] = t, stored
        r["itemid"] = int(r["itemid"])
        visible.append(r)
    visible.sort(
        key=lambda r: (r["_t"], r["_s"], str(r.get("itemid")), str(r.get("value", "")))
    )
    window = [r for r in visible if left < r["_t"] <= end]
    values = {}
    evidence = defaultdict(list)

    def add(name, value, r):
        if value is not None:
            evidence[name].append(
                {
                    "value": value,
                    "itemid": r["itemid"],
                    "table": r["table"],
                    "charttime": r["_t"].isoformat(),
                    "storetime": r["_s"].isoformat(),
                    "raw": {
                        k: r.get(k)
                        for k in (
                            "value",
                            "valuenum",
                            "valueuom",
                            "rate",
                            "rateuom",
                            "patientweight",
                            "specimen_id",
                        )
                        if k in r
                    },
                }
            )

    for r in window:
        i, n = r["itemid"], number(r.get("valuenum"))
        unit = str(r.get("valueuom", "")).lower().replace(" ", "")
        if r["table"] == "labevents":
            name = {
                50912: "creatinine",
                52546: "creatinine",
                50885: "bilirubin",
                53089: "bilirubin",
                51265: "platelet",
                53189: "platelet",
            }.get(i)
            if name and n is not None and n >= 0:
                allowed = {
                    "platelet": {"k/ul", "10^3/ul", "10^9/l"},
                    "creatinine": {"mg/dl"},
                    "bilirubin": {"mg/dl"},
                }[name]
                if unit in allowed:
                    add(name, n, r)
                else:
                    flags.add("unsupported_lab_unit")
        elif (
            r["table"] == "chartevents"
            and i in MAP_ITEMS
            and n is not None
            and 0 < n < 300
        ):
            if unit in ("mmhg", ""):
                add("map", n, r)
        elif r["table"] == "inputevents" and i in VASO_ITEMS:
            # Rewritten entries are explicitly invalidated in MIMIC.
            if str(r.get("statusdescription", "")).lower() == "rewritten":
                continue
            dose = number(r.get("rate"))
            u = str(r.get("rateuom", "")).lower().replace(" ", "").replace("µ", "u")
            if dose is None or dose < 0:
                continue
            if u in ("mcg/kg/min", "ug/kg/min"):
                pass
            elif u == "mg/kg/min":
                # MIT-LCP norepinephrine correction for two known weight=1 rows.
                dose *= (
                    1 if i == 221906 and number(r.get("patientweight")) == 1 else 1000
                )
            elif (
                u in ("mcg/min", "ug/min")
                and number(r.get("patientweight"))
                and float(r["patientweight"]) > 0
            ):
                dose /= float(r["patientweight"])
            else:
                flags.add("unsupported_vaso_unit")
                continue
            add(VASO_ITEMS[i], dose, r)
            flags.add("vaso_recorded_rate_at_start_no_future_duration")

    # Blood gases require explicit arterial specimen from the SAME specimen_id.
    specimens = defaultdict(list)
    for r in visible:
        if r["table"] == "labevents" and r.get("specimen_id"):
            specimens[str(r["specimen_id"])].append(r)
    for group in specimens.values():
        if not any(
            r["itemid"] == 52033 and str(r.get("value", "")).strip().upper() == "ART."
            for r in group
        ):
            continue
        for po in group:
            p = number(po.get("valuenum"))
            if (
                po["itemid"] != 50821
                or p is None
                or p <= 0
                or not left < po["_t"] <= end
            ):
                continue
            if "".join(str(po.get("valueuom", "")).lower().split()) != "mmhg":
                flags.add("unsupported_po2_unit")
                continue
            fio = [
                r
                for r in group
                if r["itemid"] == 50816
                and r["_t"] <= po["_t"]
                and _fio2(r.get("valuenum")) is not None
            ]
            if not fio:
                fio = [
                    r
                    for r in visible
                    if r["table"] == "chartevents"
                    and r["itemid"] == 223835
                    and po["_t"] - timedelta(hours=4) <= r["_t"] <= po["_t"]
                    and _fio2(r.get("valuenum")) is not None
                ]
            if not fio:
                flags.add("arterial_po2_without_prior_fio2")
                continue
            fr = max(fio, key=lambda r: (r["_t"], r["_s"]))
            support = [
                r
                for r in visible
                if r["table"] == "chartevents"
                and r["itemid"] in {226732, 223849, 229314}
                and po["_t"] - timedelta(hours=4) <= r["_t"] <= po["_t"]
            ]
            # Last device observation overrides an older mode (e.g., extubation).
            ventilated = False
            if support:
                latest = max(r["_t"] for r in support)
                ventilated = any(
                    str(r.get("value", "")).strip()
                    in INVASIVE_MODES | {"Endotracheal tube"}
                    for r in support
                    if r["_t"] == latest
                )
            else:
                flags.add("respiratory_support_unknown_scored_without_support")
            name = "pf_vent" if ventilated else "pf_novent"
            add(name, p / _fio2(fr["valuenum"]), po)
            evidence[name][-1]["fio2_source"] = {
                k: fr.get(k) for k in ("itemid", "charttime", "storetime", "valuenum")
            }
            evidence[name][-1]["specimen_source"] = [
                {
                    k: r.get(k)
                    for k in (
                        "itemid",
                        "charttime",
                        "storetime",
                        "value",
                        "specimen_id",
                    )
                }
                for r in group
                if r["itemid"] == 52033
            ]
            evidence[name][-1]["support_evidence"] = [
                {k: r.get(k) for k in ("itemid", "charttime", "storetime", "value")}
                for r in support
            ]

    # GCS: group at same charttime; only the immediately preceding group (<6h)
    # can fill missing components, as in the MIT-LCP query.
    gcs_groups = defaultdict(dict)
    for r in visible:
        if r["table"] == "chartevents" and r["itemid"] in GCS_ITEMS:
            gcs_groups[r["_t"]][r["itemid"]] = r
    previous_t, previous = None, {}
    for t, current in sorted(gcs_groups.items()):
        prev = previous if previous_t and t - previous_t < timedelta(hours=6) else {}
        vals = {}
        component_sources = {}
        for item, normal in ((223900, 5), (223901, 6), (220739, 4)):
            # On recovery from intubated verbal=0, previous low motor/eyes
            # cannot represent an unsedated examination (MIT-LCP special case).
            was_ett = prev.get(223900, {}).get("value") == "No Response-ETT"
            row = current.get(
                item, None if was_ett and item != 223900 else prev.get(item)
            )
            n = number(row.get("valuenum")) if row else None
            if item == 223900 and row and row.get("value") == "No Response-ETT":
                n = 0
            lower = (
                0
                if item == 223900 and row and row.get("value") == "No Response-ETT"
                else 1
            )
            vals[item] = n if n is not None and lower <= n <= normal else None
            component_sources[item] = (
                None
                if row is None
                else {
                    k: row.get(k)
                    for k in ("itemid", "charttime", "storetime", "value", "valuenum")
                }
            )
        if left < t <= end:
            if vals[223900] == 0:
                gcs = 15
                flags.add("gcs_ett_default_15")
            else:
                if any(v is None for v in vals.values()):
                    flags.add("gcs_partial_components_default_normal")
                gcs = sum(
                    vals[i] if vals[i] is not None else n
                    for i, n in ((223900, 5), (223901, 6), (220739, 4))
                )
            source = next(iter(current.values()))
            add("gcs", gcs, source)
            evidence["gcs"][-1]["components_observed"] = vals
            evidence["gcs"][-1]["component_sources"] = component_sources
        previous_t, previous = t, current

    urine = []
    for r in window:
        if r["table"] != "outputevents" or r["itemid"] not in URINE_ITEMS:
            continue
        n = number(r.get("value"))
        if n is not None and n < 0 and r["itemid"] != 227488:
            flags.add("negative_urine_output_excluded")
            continue
        if n is not None and str(r.get("valueuom", "")).lower() in ("ml", "milliliter"):
            urine.append((r["_t"], -abs(n) if r["itemid"] == 227488 else n, r))
    # A 24h observation span plus regular documentation is required. No
    # extrapolation from short windows, and no "no rows means zero output".
    times = sorted({t for t, _, _ in urine})
    covered = (
        hour_index >= 24
        and len(times) >= 2
        and times[0] <= left + timedelta(hours=2)
        and times[-1] >= end - timedelta(hours=2)
        and max(b - a for a, b in itertools.pairwise(times)) <= timedelta(hours=6)
    )
    if covered and sum(v for _, v, _ in urine) >= 0:
        values["urine_24h"] = sum(v for _, v, _ in urine)
        for _, v, r in urine:
            add("urine_24h", v, r)
    else:
        flags.add("urine_24h_insufficient_documented_coverage")
    for name, rows in evidence.items():
        if name != "urine_24h":
            agg = (
                min
                if name in ("pf_vent", "pf_novent", "platelet", "map", "gcs")
                else max
            )
            values[name] = agg(r["value"] for r in rows)
    components = score_components(values)
    missing = [k for k, v in components.items() if v is None]
    return {
        "stay_id": int(stay_id),
        "hour_index": hour_index,
        "window_start": max(start, left).isoformat(),
        "window_end": end.isoformat(),
        "window_left_open": left >= start,
        "partial_window": hour_index < 24,
        "components": components,
        "sofa_total": sum(v or 0 for v in components.values()),
        "missing_components": missing,
        "n_observed_components": 6 - len(missing),
        "quality_flags": sorted(flags),
        "inputs": values,
        "evidence": dict(evidence),
        "priority_weight": round(1 + sum(v or 0 for v in components.values()) / 10, 4),
    }
