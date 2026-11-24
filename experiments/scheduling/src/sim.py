"""ICU 床位滚动调度仿真核心（真实到达流 / 同池同资源）。

方法：
  M0_fcfs            先到先得，首个可行床
  M1_greedy_sofa     按 SOFA 降序，首个可行床
  M2_greedy_priority 按仓内 GBDT 权重降序，首个可行床
  M3_greedy_reserve  按 SOFA 降序 + 隔离/呼吸机床位预留
  M4_cpsat_ws        CP-SAT 加权和（收益 + 占用 − 分区 − 隔离挤占 − 搬移）
  M5_cpsat_lex       CP-SAT 词典序（先高危人数，再总收益）
  M6_cpsat_eps       ε 约束（高危未安置上限）→ Pareto
  M7_rolling         滚动再优化（允许已入科病人换床，带搬移惩罚）

资源：20 床（ISO 4 / MICU 4 / SICU 4 / CCU 4 / NICU 4），呼吸机 8 台（按通气时长占用设备，
不是整段住院占用），隔离床 4 张（隔离病人硬约束；非隔离病人用隔离床重罚）。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
from ortools.sat.python import cp_model

STEP_H = 2
N_BEDS = 20
N_VENTS = 8
BED_LAYOUT = {"ISO": [1, 2, 3, 4, 5], "MICU": [6, 7, 8, 9], "SICU": [10, 11, 12, 13],
              "CCU": [14, 15, 16, 17], "NICU": [18, 19, 20]}
ISO_BEDS = {1, 2, 3, 4, 5}  # 20 床中 5 张隔离单间（25%）
VENT_BEDS: set[int] = set()  # 呼吸机是设备约束（见 N_VENTS），不绑定具体床位
ZONE_OF_BED = {b: z for z, beds in BED_LAYOUT.items() for b in beds}
ISO_PENALTY = 300  # 非隔离病人占隔离床的惩罚（隔离床是稀缺专科资源）


@dataclass
class Patient:
    pid: int
    stay_id: int
    arrival: datetime
    depart: datetime          # 占位：真正出院时刻在入院时改写为 admit + los_h
    los_h: float
    zone: str
    need_iso: bool
    vent_hours: float
    sofa0: float
    priority: float
    benefit: int
    high_risk: bool
    admit: datetime | None = None
    moves: int = 0

    @property
    def need_vent(self) -> bool:
        return self.vent_hours > 0


@dataclass
class Episode:
    method: str
    scenario: str
    patients: dict[int, Patient]
    steps: list[dict] = field(default_factory=list)
    moved: int = 0
    displaced: int = 0
    decisions: int = 0
    fallbacks: int = 0
    solve_ms: list[float] = field(default_factory=list)
    horizon_end: datetime | None = None


def feasible(p: Patient, bed: int) -> bool:
    if p.need_iso and bed not in ISO_BEDS:
        return False
    return True


def beds_in_use_by_device(occupant: dict[int, Patient], t: datetime) -> int:
    n = 0
    for p in occupant.values():
        if p.vent_hours <= 0 or p.admit is None:
            continue
        elapsed = (t - p.admit).total_seconds() / 3600.0
        if 0 <= elapsed < p.vent_hours:
            n += 1
    return n


# ─────────────────────────── greedy ───────────────────────────
def greedy_assign(free: list[int], queue: list[Patient], *, key: str,
                  reserve: bool = False, device_free: int = N_VENTS) -> list[tuple[Patient, int]]:
    free_set = set(free)
    iso_waiting = sum(1 for p in queue if p.need_iso)
    vent_waiting = sum(1 for p in queue if p.need_vent)
    if key == "sofa":
        order = sorted(queue, key=lambda p: (-p.sofa0, p.arrival))
    elif key == "priority":
        order = sorted(queue, key=lambda p: (-p.priority, p.arrival))
    else:
        order = sorted(queue, key=lambda p: p.arrival)
    out = []
    for p in order:
        cands = [b for b in free_set if feasible(p, b)]
        if not cands:
            continue
        if p.need_vent and device_free <= 0:
            continue
        if reserve:
            iso_free = sum(1 for b in free_set if b in ISO_BEDS)
            if not p.need_iso and iso_free <= iso_waiting:
                cands = [b for b in cands if b not in ISO_BEDS] or []
            if cands and not p.need_vent:
                if device_free <= vent_waiting:
                    pass  # 设备由 use 计数控制，无需改床位
        if not cands:
            continue
        b = min(cands, key=lambda x: ((x in ISO_BEDS) and not p.need_iso,
                                      ZONE_OF_BED[x] != p.zone, x))
        free_set.discard(b)
        iso_waiting = max(0, iso_waiting - int(p.need_iso))
        vent_waiting = max(0, vent_waiting - int(p.need_vent))
        if p.need_vent:
            device_free -= 1
        out.append((p, b))
    return out


# ─────────────────────────── CP-SAT ───────────────────────────
def cp_assign(free: list[int], queue: list[Patient], *, mode: str = "ws",
              occ_weight: int = 5, zone_penalty: int = 25, move_penalty: int = 40,
              admitted_bed: dict[int, int] | None = None, allow_moves: bool = False,
              time_limit: float = 2.0, eps_cap: int | None = None,
              device_free: int = N_VENTS) -> list[tuple[Patient, int]]:
    if not free or not queue:
        return []
    n, m = len(queue), len(free)
    model = cp_model.CpModel()
    x = {(i, j): model.NewBoolVar(f"x{i}_{j}") for i in range(n) for j in range(m)}

    for i in range(n):
        model.Add(sum(x[i, j] for j in range(m)) <= 1)
    for j in range(m):
        model.Add(sum(x[i, j] for i in range(n)) <= 1)
    for i, p in enumerate(queue):
        for j, b in enumerate(free):
            if not feasible(p, b):
                model.Add(x[i, j] == 0)

    vent_terms = [x[i, j] for i, p in enumerate(queue)
                  if p.need_vent and (not admitted_bed or p.pid not in admitted_bed)
                  for j in range(m)]
    if vent_terms:
        model.Add(sum(vent_terms) <= max(0, device_free))
    if allow_moves and admitted_bed:
        for i, p in enumerate(queue):
            if p.pid in admitted_bed:
                model.Add(sum(x[i, j] for j in range(m)) == 1)  # 在科病人不得被挤出

    hi_idx = [i for i, p in enumerate(queue) if p.high_risk]
    hi_served = model.NewIntVar(0, max(1, len(hi_idx)), "hi")
    model.Add(hi_served == sum(x[i, j] for i in hi_idx for j in range(m)))

    benefit_terms = [queue[i].benefit * x[i, j] for i in range(n) for j in range(m)]
    mismatch_terms = [x[i, j] for i, p in enumerate(queue) for j, b in enumerate(free)
                      if ZONE_OF_BED[b] != p.zone]
    iso_squat = [x[i, j] for i, p in enumerate(queue) for j, b in enumerate(free)
                 if (b in ISO_BEDS) and not p.need_iso]
    move_terms = []
    if allow_moves and admitted_bed:
        for i, p in enumerate(queue):
            cur = admitted_bed.get(p.pid)
            if cur is None:
                continue
            for j, b in enumerate(free):
                if b != cur:
                    move_terms.append(x[i, j])

    base = sum(benefit_terms) + occ_weight * sum(x.values())
    penalties = (zone_penalty * sum(mismatch_terms) + ISO_PENALTY * sum(iso_squat)
                 + move_penalty * sum(move_terms))
    if mode == "lex":
        model.Maximize(100000 * hi_served + sum(benefit_terms) + occ_weight * sum(x.values())
                       - ISO_PENALTY * sum(iso_squat) - move_penalty * sum(move_terms))
    elif mode == "eps":
        model.Maximize(base - penalties)
        if eps_cap is not None:
            # 可安置的高危上限是 min(高危人数, 空床数)；ε 必须在这个可行范围内取，
            # 否则约束恒不可行 → 求解返回空解 → 该步不分配（会污染整条轨迹）
            _reach = min(len(hi_idx), m)
            model.Add(hi_served >= max(0, _reach - eps_cap))
    else:
        model.Maximize(60 * hi_served + base - penalties)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return []
    return [(queue[i], free[j]) for i in range(n) for j in range(m) if solver.Value(x[i, j])]


# ─────────────────────────── 仿真主循环 ───────────────────────────
def run_episode(scenario: dict, method: str, *, step_h: int = STEP_H,
                warmup_days: int = 7, time_limit: float = 2.0,
                eps_cap: int | None = None) -> Episode:
    """跑一个场景 × 一个方法。

    eps_cap 仅对 M6_cpsat_eps 生效：高危未安置人数上限 ε。
    为 None 时保持原行为（空床≥3 时 ε=0，否则 ε=1），即默认轨迹不变。
    """
    pats: dict[int, Patient] = {}
    for r in scenario["patients"]:
        pats[r["pid"]] = Patient(
            pid=r["pid"], stay_id=r["stay_id"],
            arrival=datetime.fromisoformat(r["arrival"]),
            depart=datetime.fromisoformat(r["depart"]),
            los_h=float(r["los_h"]), zone=r["zone"],
            need_iso=r["need_iso"], vent_hours=float(r.get("vent_hours", 0.0)),
            sofa0=r["sofa0"], priority=r["priority"], benefit=r["benefit"],
            high_risk=r["high_risk"])
    arrivals = sorted(pats.values(), key=lambda p: p.arrival)
    t0 = datetime.fromisoformat(scenario["t0"])
    t1 = datetime.fromisoformat(scenario["t1"])
    warm_until = t0 + timedelta(days=warmup_days)

    ep = Episode(method=method, scenario=scenario["name"], patients=pats, horizon_end=t1)
    occupant: dict[int, Patient] = {}
    queue: list[Patient] = []
    ai = 0
    t = t0
    while t < t1:
        for b in [b for b, p in occupant.items() if p.depart <= t]:
            del occupant[b]
        while ai < len(arrivals) and arrivals[ai].arrival <= t:
            queue.append(arrivals[ai])
            ai += 1
        free = [b for b in range(1, N_BEDS + 1) if b not in occupant]
        if queue and free:
            dev_free = N_VENTS - beds_in_use_by_device(occupant, t)
            if method == "M0_fcfs":
                assigned = greedy_assign(free, queue, key="fcfs", device_free=dev_free)
            elif method == "M1_greedy_sofa":
                assigned = greedy_assign(free, queue, key="sofa", device_free=dev_free)
            elif method == "M2_greedy_priority":
                assigned = greedy_assign(free, queue, key="priority", device_free=dev_free)
            elif method == "M3_greedy_reserve":
                assigned = greedy_assign(free, queue, key="sofa", reserve=True, device_free=dev_free)
            elif method == "M7_rolling":
                admitted_pids = {p.pid for p in occupant.values()}
                cand = queue + list(occupant.values())
                if len(cand) <= 1 or len(free) <= 1:
                    assigned = greedy_assign(free, queue, key="sofa", device_free=dev_free)
                else:
                    cur = {p.pid: b for b, p in occupant.items()}
                    st = time.perf_counter()
                    res = cp_assign(list(range(1, N_BEDS + 1)), cand, mode="ws",
                                    allow_moves=True, admitted_bed=cur, move_penalty=40,
                                    time_limit=time_limit, device_free=dev_free)
                    ep.solve_ms.append(1000 * (time.perf_counter() - st))
                    ep.decisions += 1
                    if not res:
                        # 求解超时/不可行：在科病人原地不动，只用贪心补空床
                        # （否则空解会被误判为"把全部在科病人挤出"）
                        ep.fallbacks += 1
                        assigned = greedy_assign(free, queue, key="sofa", device_free=dev_free)
                        res = None
                    if res is None:
                        pass
                    else:
                        new_occ = {b: p for p, b in res}
                        placed_pids = {p.pid for p, _ in res}
                        for p, b in res:
                            if p.admit is None:
                                p.admit = t
                                p.depart = t + timedelta(hours=p.los_h)
                            if p.pid in cur and cur[p.pid] != b:
                                p.moves += 1
                                ep.moved += 1
                        misplaced = [pats[pid] for pid in admitted_pids - placed_pids]
                        if misplaced:
                            ep.fallbacks += 1
                        queue = [p for p in queue if p.pid not in placed_pids] + misplaced
                        ep.displaced += len(misplaced)
                        occupant = new_occ
                        assigned = []
            else:
                if len(queue) <= 1 or len(free) <= 1:
                    assigned = greedy_assign(free, queue, key="sofa", device_free=dev_free)
                else:
                    mode = {"M4_cpsat_ws": "ws", "M5_cpsat_lex": "lex",
                            "M6_cpsat_eps": "eps"}[method]
                    if method == "M6_cpsat_eps":
                        cap = (eps_cap if eps_cap is not None
                               else (0 if len(free) >= 3 else 1))
                    else:
                        cap = None
                    st = time.perf_counter()
                    assigned = cp_assign(free, queue[:40], mode=mode, eps_cap=cap,
                                         time_limit=time_limit, device_free=dev_free)
                    ep.solve_ms.append(1000 * (time.perf_counter() - st))
                    ep.decisions += 1
            for p, b in assigned:
                occupant[b] = p
                if p.admit is None:
                    p.admit = t
                    p.depart = t + timedelta(hours=p.los_h)
            if assigned:
                done = {p.pid for p, _ in assigned}
                queue = [p for p in queue if p.pid not in done]

        if t >= warm_until:
            hr_wait = [(t - p.arrival).total_seconds() / 3600.0 for p in queue if p.high_risk]
            ep.steps.append({
                "t": t.isoformat(), "occupancy": len(occupant), "queue": len(queue),
                "hr_waiting": len(hr_wait), "hr_wait_sum": float(sum(hr_wait)),
                "iso_used": sum(1 for b in occupant if b in ISO_BEDS),
                "vent_used": sum(1 for p in occupant.values() if p.need_vent),
                "vent_devices": beds_in_use_by_device(occupant, t),
                "assigned": "|".join(str(p.pid) for p in occupant.values()),
            })
        t += timedelta(hours=step_h)
    return ep


# ─────────────────────────── 指标 ───────────────────────────
def _gini(xs: list[float]) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    n, s = len(xs), sum(xs)
    if s <= 0:
        return 0.0
    cum = sum((i + 1) * x for i, x in enumerate(xs))
    return float((2 * cum) / (n * s) - (n + 1) / n)


def summarize(ep: Episode) -> dict:
    t1 = ep.horizon_end
    rec = {"method": ep.method, "scenario": ep.scenario, "moved": ep.moved,
           "displaced": ep.displaced, "decisions": ep.decisions,
           "fallbacks": ep.fallbacks,
           "solve_ms_mean": float(np.mean(ep.solve_ms)) if ep.solve_ms else 0.0,
           "solve_ms_total": float(np.sum(ep.solve_ms)) if ep.solve_ms else 0.0}
    waits_all, waits_hr, unassigned, benefit_served = [], [], 0, 0.0
    for p in ep.patients.values():
        end = p.admit if p.admit is not None else t1
        w = (end - p.arrival).total_seconds() / 3600.0
        if p.admit is None:
            unassigned += 1
        else:
            benefit_served += p.benefit
        waits_all.append(w)
        if p.high_risk:
            waits_hr.append(w)
    rec.update({
        "n_patients": len(ep.patients), "unassigned": unassigned,
        "wait_mean": float(np.mean(waits_all)), "wait_median": float(np.median(waits_all)),
        "hr_n": len(waits_hr),
        "hr_wait_mean": float(np.mean(waits_hr)) if waits_hr else 0.0,
        "hr_wait_median": float(np.median(waits_hr)) if waits_hr else 0.0,
        "hr_wait_p90": float(np.percentile(waits_hr, 90)) if waits_hr else 0.0,
        "hr_within6": float(np.mean([w <= 6 for w in waits_hr])) if waits_hr else 0.0,
        "avg_queue": float(np.mean([s["queue"] for s in ep.steps])) if ep.steps else 0.0,
        "max_queue": int(max((s["queue"] for s in ep.steps), default=0)),
        "utilization": float(np.mean([s["occupancy"] for s in ep.steps]) / N_BEDS) if ep.steps else 0.0,
        "vent_device_util": float(np.mean([s["vent_devices"] for s in ep.steps]) / N_VENTS) if ep.steps else 0.0,
        "iso_util": float(np.mean([s["iso_used"] for s in ep.steps]) / len(ISO_BEDS)) if ep.steps else 0.0,
        "benefit_served": benefit_served,
        "gini_hr_wait": _gini(waits_hr),
    })
    return rec
