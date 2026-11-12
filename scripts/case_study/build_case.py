"""Reproduce the attachment-defined ICU scheduling case without changing project code.

Real MIMIC component snapshots and historical movements are inputs. Capacity,
concurrent arrivals and discharges are declared simulation assumptions.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from collections import Counter
from datetime import datetime
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path

from ortools.sat.python import cp_model
import ortools

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports/icu_case_20261112"
SAMPLE = ROOT / "artifacts/sofa_sample/sofa_sample.json"
HISTORY = OUT / "mimic_history.json"
THEORY = None
# The locally extracted history supplies the ordered cohort, not repository data.
IDS = []
COMPONENTS = ("coagulation", "liver", "renal")
ZONES = {1: "MICU", 2: "SICU", 3: "SICU", 4: "CCU", 5: "CCU", 6: "NICU"}
PARAM = dict(n_beds=6, n_isolation_beds=0, n_ventilators=None,
             isolation_mode="off_missing_labels", ventilator_mode="off_missing_labels",
             ward_capacity=2, theta=5, eta=6, K=1, max_moves=2,
             max_transfers=0, retain_occupied=True, occupancy_ratio=1,
             occupancy_floor=6, solver_seed=0, max_time_seconds=10, step_hours=2)


def zone(careunit):
    if "Medical" in careunit:
        return "MICU"
    if "SICU" in careunit or "Surgical" in careunit or "Trauma" in careunit:
        return "SICU"
    if "Coronary" in careunit or "Cardiac" in careunit:
        return "CCU"
    if "Neuro" in careunit:
        return "NICU"
    raise ValueError(f"Declare a mapping for {careunit!r}")


def load_inputs():
    payload = json.loads(SAMPLE.read_text(encoding="utf-8"))
    stays = {r["stay_id"]: r for r in payload["stays"]}
    scores = {(r["stay_id"], r["hour_index"]): r for r in payload["scores"]}
    patients, evidence = {}, []
    for index, sid in enumerate(IDS, 1):
        pid = f"P{index:02}"
        patients[pid] = dict(pid=pid, stay_id=sid, **{
            k: stays[sid][k] for k in ("hadm_id", "subject_id", "first_careunit", "intime", "outtime")},
            preferred_zone=zone(stays[sid]["first_careunit"]),
            needs_isolation=None, needs_ventilator=None)
        for hour in range(24, 38, 2):
            r = scores[sid, hour]
            assert all(r["components"][k] is not None for k in COMPONENTS), (pid, hour)
            # Preserve source evidence and reject values not available by the decision.
            selected = {k: r["evidence"].get(k, []) for k in
                        ("platelet", "bilirubin", "creatinine", "urine_24h")}
            end = datetime.fromisoformat(r["window_end"])
            for items in selected.values():
                for item in items:
                    for clock in ("charttime", "storetime"):
                        if item.get(clock):
                            assert datetime.fromisoformat(item[clock]) <= end, (pid, hour, clock)
            evidence.append(dict(pid=pid, stay_id=sid, hour=hour,
                window_start=r["window_start"], window_end=r["window_end"],
                components={k: r["components"][k] for k in COMPONENTS},
                sofa12=sum(r["components"][k] for k in COMPONENTS),
                full_sofa24=r["sofa_total"], inputs=r["inputs"], evidence=selected,
                quality_flags=r["quality_flags"]))
    return patients, {(r["pid"], r["hour"]): r for r in evidence}, evidence


def snapshot(patients, evidence, active, hour):
    # All cases have an observed 24-hour prehistory. All elapsed times are tied,
    # so their empirical CDF is 1. Final LOS/outtime never enters the optimizer.
    rows = []
    for pid in sorted(active):
        r = evidence[pid, 24 + hour]
        s = r["sofa12"]
        w = Decimal(1) + Decimal("0.6") * Decimal(s) / 12 + Decimal("0.4")
        rows.append(dict(pid=pid, score=s, weight=str(w), L_percentile=1,
                         W=int((1000 * w).to_integral_value(rounding=ROUND_FLOOR)),
                         zone=patients[pid]["preferred_zone"],
                         clinical_hour=24 + hour))
    return rows


def evaluate(rows, assignment, ward, previous):
    byid = {r["pid"]: r for r in rows}
    loads = Counter(ZONES[b] for b in assignment.values())
    return [len(assignment), sum(byid[p]["W"] for p in set(assignment) | set(ward)),
            sum(byid[p]["score"] >= PARAM["theta"] for p in ward),
            max(loads.get(z, 0) for z in set(ZONES.values())) - min(loads.get(z, 0) for z in set(ZONES.values())),
            sum(byid[p]["zone"] != ZONES[b] for p, b in assignment.items()),
            sum(p in assignment and assignment[p] != b for p, b in previous.items())]


def validate(rows, result, previous=None, ward_existing=(), bound=None):
    previous = previous or {}
    assignment, ward = result["assignment"], result["ward"]
    ids = {r["pid"] for r in rows}
    byid = {r["pid"]: r for r in rows}
    assert set(assignment) <= ids and set(ward) <= ids
    assert len(set(assignment.values())) == len(assignment)
    assert set(assignment.values()) <= set(ZONES)
    assert set(assignment).isdisjoint(ward)
    assert all(p in assignment or p in ward for p in previous), "incumbent displaced to waiting"
    assert len(ward) + len(ward_existing) <= PARAM["ward_capacity"]
    assert all(byid[p]["score"] <= PARAM["eta"] for p in ward)
    # The attachment caps NEW severe ward admissions at each decision; existing
    # ward patients are an occupancy pool, not rescored candidates.
    assert sum(byid[p]["score"] >= PARAM["theta"] for p in ward) <= PARAM["K"]
    f = evaluate(rows, assignment, ward, previous)
    assert f == result["f"]
    assert f[0] >= PARAM["occupancy_floor"] and f[5] <= PARAM["max_moves"]
    if bound:
        assert f[2] <= bound[0] and f[4] <= bound[1]
    assert sorted(ids - set(assignment) - set(ward)) == result["waiting"]


def solve(rows, previous=None, ward_existing=(), eps=(1, 6)):
    previous = previous or {}
    model = cp_model.CpModel()
    x = {(r["pid"], b): model.new_bool_var(f"x_{r['pid']}_{b}") for r in rows for b in ZONES}
    z = {r["pid"]: model.new_bool_var(f"ward_{r['pid']}") for r in rows}
    for r in rows:
        p = r["pid"]
        disposition = sum(x[p, b] for b in ZONES) + z[p]
        model.add(disposition == 1 if p in previous else disposition <= 1)
        if r["score"] > PARAM["eta"]:
            model.add(z[p] == 0)
    for b in ZONES:
        model.add(sum(x[r["pid"], b] for r in rows) <= 1)
    model.add(sum(z.values()) + len(ward_existing) <= PARAM["ward_capacity"])
    f0 = sum(x.values())
    f1 = sum(r["W"] * (sum(x[r["pid"], b] for b in ZONES) + z[r["pid"]]) for r in rows)
    f2 = sum(z[r["pid"]] for r in rows if r["score"] >= PARAM["theta"])
    f4 = sum(x[r["pid"], b] for r in rows for b in ZONES if r["zone"] != ZONES[b])
    f5 = sum(sum(x[p, b] for b in ZONES) - x[p, old] for p, old in previous.items())
    model.add(f0 >= PARAM["occupancy_floor"])
    model.add(f2 <= PARAM["K"])
    model.add(f5 <= PARAM["max_moves"])
    model.add(f2 <= eps[0])
    model.add(f4 <= eps[1])
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = PARAM["solver_seed"]
    solver.parameters.max_time_in_seconds = PARAM["max_time_seconds"]
    # The first three stages are precisely the attachment's active objectives.
    # Move and a deterministic bed preference only choose one representative.
    tie = sum((int(r["pid"][1:]) * 7 + b) * x[r["pid"], b] for r in rows for b in ZONES)
    stages = []
    for expr, sense in [(f1, "max"), (f2, "min"), (f4, "min"), (f5, "min"), (tie, "min")]:
        model.maximize(expr) if sense == "max" else model.minimize(expr)
        status = solver.solve(model)
        name = solver.status_name(status)
        stages.append(name)
        if status == cp_model.INFEASIBLE:
            return dict(status="INFEASIBLE", eps=list(eps), stages=stages)
        if status != cp_model.OPTIMAL:
            raise RuntimeError(f"Unproved solve {name}, eps={eps}")
        model.add(expr == solver.value(expr))
    assignment = {r["pid"]: b for r in rows for b in ZONES if solver.value(x[r["pid"], b])}
    ward = sorted(p for p in z if solver.value(z[p]))
    result = dict(status="OPTIMAL", eps=list(eps), stages=stages, assignment=assignment,
                  ward=ward, waiting=sorted({r["pid"] for r in rows} - set(assignment) - set(ward)))
    result["f"] = evaluate(rows, assignment, ward, previous)
    validate(rows, result, previous, ward_existing, eps)
    return result


def triple(r):
    return (-r["f"][1], r["f"][2], r["f"][4])


def nondominated(results):
    unique = {}
    for r in results:
        if r["status"] == "OPTIMAL":
            unique.setdefault(triple(r), r)
    return [unique[t] for t in sorted(unique) if not any(
        all(a <= b for a, b in zip(u, t)) and u != t for u in unique)]


def scan(rows, previous=None, ward_existing=()):
    results = [solve(rows, previous, ward_existing, (e2, e4))
               for e2 in range(PARAM["K"] + 1) for e4 in range(PARAM["n_beds"] + 1)]
    return nondominated(results), results


def select(front):
    # Frozen BEFORE computation: no severe-to-ward first, then highest service,
    # then matching. A deterministic fallback handles infeasible zero-severe.
    return min(front, key=lambda r: (r["f"][2], -r["f"][1], r["f"][4], r["f"][5]))


def independent_static_front(rows):
    """Enumerate patient subsets, without using the CP-SAT model or metrics.

    With no incumbents/ISO, minimum mismatch for a fixed ICU subset is
    m - sum(min(zone_demand, zone_capacity)). Other permutations only increase
    mismatch and cannot create nondominated active-objective vectors.
    """
    byid = {r["pid"]: r for r in rows}
    caps = Counter(ZONES.values())
    vectors, count = set(), 0
    for icu in itertools.combinations(byid, PARAM["n_beds"]):
        pool = [p for p in byid if p not in icu and byid[p]["score"] <= PARAM["eta"]]
        demand = Counter(byid[p]["zone"] for p in icu)
        mismatch = PARAM["n_beds"] - sum(min(caps[k], demand[k]) for k in caps)
        for size in range(PARAM["ward_capacity"] + 1):
            for ward in itertools.combinations(pool, size):
                severe = sum(byid[p]["score"] >= PARAM["theta"] for p in ward)
                if severe > PARAM["K"]:
                    continue
                count += 1
                service = sum(byid[p]["W"] for p in icu + ward)
                vectors.add((-service, severe, mismatch))
    front = sorted(t for t in vectors if not any(u != t and all(a <= b for a, b in zip(u, t)) for u in vectors))
    return dict(method="ICU/ward subset enumeration plus exact zone matching lower bound",
                feasible_patient_partitions=count, distinct_vectors=len(vectors), front=front)


def rule_baseline(rows):
    """Declared synthetic first-come rule; never described as a doctor record."""
    assignment, ward, free = {}, [], set(ZONES)
    # P01..P12 are fixed scenario queue order, not historical arrival order.
    for r in rows:
        if not free:
            continue
        matches = [b for b in sorted(free) if ZONES[b] == r["zone"]]
        b = matches[0] if matches else min(free)
        assignment[r["pid"]] = b
        free.remove(b)
    for r in rows:
        if r["pid"] in assignment or len(ward) >= PARAM["ward_capacity"]:
            continue
        if r["score"] <= PARAM["eta"] and (r["score"] < PARAM["theta"] or
            sum(next(q["score"] for q in rows if q["pid"] == p) >= PARAM["theta"] for p in ward) < PARAM["K"]):
            ward.append(r["pid"])
    result = dict(status="RULE_BASELINE", assignment=assignment, ward=ward,
                  waiting=sorted({r["pid"] for r in rows} - set(assignment) - set(ward)))
    result["f"] = evaluate(rows, assignment, ward, {})
    validate(rows, result)
    return result


def run_case():
    patients, evidence, evidence_list = load_inputs()
    static_rows = snapshot(patients, evidence, patients, 0)
    front, grid = scan(static_rows)
    reference = solve(static_rows)
    assert triple(reference) in {triple(r) for r in front}
    control = independent_static_front(static_rows)
    assert control["front"] == [list(triple(r)) for r in front] or control["front"] == [triple(r) for r in front]
    for index, r in enumerate(sorted(front, key=lambda r: (r["f"][2], r["f"][4], -r["f"][1])), 1):
        r["name"] = f"S{index}"
    baseline = rule_baseline(static_rows)
    # Rolling uses the same 12 people but only 10 are visible initially.
    # Future arrivals/discharges stay in the simulator, never in solve().
    arrivals = {0: set(patients) - {"P02", "P06"}, 2: {"P02"}, 6: {"P06"}}
    discharge_events = {4: {"P01"}, 8: {"P05"}, 12: {"P08"}}
    occupied, waiting, pending, discharged, ward_total = {}, set(), set(patients), set(), set()
    history = []
    for hour in range(0, 14, 2):
        previous_snapshot = dict(occupied)
        event_out = set()
        for p in discharge_events.get(hour, set()):
            # Each scripted departure must actually release an occupied ICU bed.
            assert p in occupied, (hour, p, occupied)
            occupied.pop(p)
            discharged.add(p)
            event_out.add(p)
        event_in = arrivals.get(hour, set())
        assert event_in <= pending
        pending -= event_in
        waiting |= event_in
        predecision = dict(occupied)
        active = set(occupied) | waiting
        rows = snapshot(patients, evidence, active, hour)
        current_front, current_grid = scan(rows, predecision, ward_total)
        assert current_front
        execution = select(current_front)
        occupied = dict(execution["assignment"])
        waiting = set(execution["waiting"])
        old_ward = set(ward_total)
        ward_total |= set(execution["ward"])
        partitions = [set(occupied), waiting, pending, discharged, ward_total]
        assert set.union(*partitions) == set(patients)
        assert sum(map(len, partitions)) == len(patients)
        history.append(dict(hour=hour, score_hour=24+hour, arrivals=sorted(event_in),
            discharges=sorted(event_out), previous_snapshot=previous_snapshot,
            predecision=predecision, rows=rows, old_ward=sorted(old_ward),
            executed=execution, front=current_front, grid=current_grid,
            occupied=dict(occupied), waiting=sorted(waiting), pending=sorted(pending),
            discharged_total=sorted(discharged), ward_total=sorted(ward_total),
            patient_conservation=True))
        print(f"rolling hour={hour}: f={execution['f']}, ward={sorted(ward_total)}, waiting={sorted(waiting)}", flush=True)
    # Recheck the STORED snapshots after all later events have occurred.
    # This catches mutable-reference bugs that per-step validation cannot catch.
    for saved in history:
        assert saved["occupied"] == saved["executed"]["assignment"]
        assert len(saved["occupied"]) == saved["executed"]["f"][0]
        states = [set(saved[k]) for k in
                  ("occupied", "waiting", "pending", "discharged_total", "ward_total")]
        assert set.union(*states) == set(patients)
        assert sum(map(len, states)) == len(patients)
        validate(saved["rows"], saved["executed"], saved["predecision"], saved["old_ward"])
    return dict(schema_version=1, generated_date="2026-11-12", params=PARAM,
        bed_zones=ZONES, patients=patients, evidence=evidence_list,
        input_sources=dict(sample=str(SAMPLE), sample_sha256=hashlib.sha256(SAMPLE.read_bytes()).hexdigest(),
                          history=str(HISTORY), history_sha256=hashlib.sha256(HISTORY.read_bytes()).hexdigest(),
                          theory=str(THEORY) if THEORY else None,
                          theory_sha256=hashlib.sha256(THEORY.read_bytes()).hexdigest() if THEORY else None),
        software=dict(ortools=ortools.__version__, seed=0, workers=1),
        static=dict(rows=static_rows, front=front, grid=grid, reference=reference,
                    selected=select(front), baseline=baseline, independent_validation=control),
        rolling=dict(arrival_schedule={k: sorted(v) for k,v in arrivals.items()},
            discharge_schedule={k: sorted(v) for k,v in discharge_events.items()}, history=history),
        checks=dict(all_solution_metrics_recomputed=True, hard_constraints=True,
            static_front_matches_independent_enumeration=True,
            all_solver_stages_proven_optimal=True, rolling_patient_conservation=True,
            no_future_score_evidence=True, final_los_not_used=True,
            stored_snapshots_immutable_and_conserved=True))


def main():
    global OUT, SAMPLE, HISTORY, THEORY, IDS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=SAMPLE, help="Local prepared SOFA JSON")
    parser.add_argument("--history", type=Path, default=None, help="Local MIMIC history JSON with ordered requested_stay_ids")
    parser.add_argument("--theory", type=Path, help="Optional local theory report, recorded by hash")
    parser.add_argument("--output", type=Path, default=OUT, help="Output directory; keep generated patient data outside Git")
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    OUT, SAMPLE, THEORY = args.output.resolve(), args.input.resolve(), args.theory
    HISTORY = (args.history or OUT / "mimic_history.json").resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.report_only:
        data = json.loads((OUT / "case_results.json").read_text(encoding="utf-8"))
        if args.history:
            data["input_sources"]["history"] = str(HISTORY)
    else:
        if not SAMPLE.is_file() or not HISTORY.is_file():
            parser.error("Provide existing local --input and --history files; patient data is not bundled")
        if THEORY and not THEORY.is_file():
            parser.error("--theory must name an existing local report")
        history = json.loads(HISTORY.read_text(encoding="utf-8"))
        IDS = history["requested_stay_ids"]
        if len(IDS) != 12 or len(set(IDS)) != 12:
            parser.error("This fixed presentation scenario requires exactly 12 distinct ordered stays")
        data = run_case()
        (OUT / "case_results.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print("static front:", [(r.get("name"), r["f"]) for r in data["static"]["front"]])
    # Human-readable report is generated separately from these verified results.
    report_module = Path(__file__).with_name("write_report.py")
    if report_module.exists():
        import runpy
        writer = runpy.run_path(str(report_module))
        writer["write_report"](data, OUT)


if __name__ == "__main__":
    main()
