"""S2-MOO phase 3: payoff table, epsilon grid, nondominated set, hypervolume.

Pure helpers are DB-free (unit-tested).  Orchestration calls ``run_assignment``.
"""

from __future__ import annotations

import csv
import itertools
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

OBJECTIVE_SENSES: dict[str, str] = {
    "occupancy": "max",
    "high_risk": "max",
    "wait": "max",
    "overload": "min",
    "zone_mismatch": "min",
    "move": "min",
    "balance": "min",
}

DEFAULT_OBJECTIVES = tuple(OBJECTIVE_SENSES)
DEFAULT_GRID_OBJECTIVES = ("occupancy", "high_risk", "overload", "balance")
DEFAULT_PRIMARY = "wait"

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "moo"


@dataclass(frozen=True)
class ObjectivePoint:
    """One feasible objective vector plus metadata."""

    values: dict[str, int]
    source: str
    status: str = "UNKNOWN"
    wall_time_seconds: float = 0.0
    extras: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "values": dict(self.values),
            "source": self.source,
            "status": self.status,
            "wall_time_seconds": self.wall_time_seconds,
            "extras": dict(self.extras or {}),
        }


def is_better(a: float, b: float, sense: str) -> bool:
    return a > b if sense == "max" else a < b


def dominates(
    left: Mapping[str, int | float],
    right: Mapping[str, int | float],
    *,
    senses: Mapping[str, str] | None = None,
) -> bool:
    """True if ``left`` Pareto-dominates ``right`` (strictly better in ≥1 dim)."""
    sense_map = senses or OBJECTIVE_SENSES
    keys = [k for k in left if k in right and k in sense_map]
    if not keys:
        return False
    weakly_better = True
    strictly = False
    for key in keys:
        sense = sense_map[key]
        lv, rv = float(left[key]), float(right[key])
        if is_better(lv, rv, sense):
            strictly = True
        elif lv != rv:
            weakly_better = False
            break
    return weakly_better and strictly


def filter_nondominated(
    points: Sequence[ObjectivePoint],
    *,
    senses: Mapping[str, str] | None = None,
) -> list[ObjectivePoint]:
    feasible = [p for p in points if p.values and p.status in ("OPTIMAL", "FEASIBLE")]
    kept: list[ObjectivePoint] = []
    for cand in feasible:
        if any(
            dominates(other.values, cand.values, senses=senses)
            for other in feasible
            if other is not cand
        ):
            continue
        if any(other.values == cand.values for other in kept):
            continue
        kept.append(cand)
    return kept


def normalize_for_maximization(
    values: Mapping[str, int | float],
    *,
    ideal: Mapping[str, float],
    nadir: Mapping[str, float],
    senses: Mapping[str, str],
) -> dict[str, float]:
    """Map each objective to [0, 1] where 1 is best (ideal)."""
    out: dict[str, float] = {}
    for name, sense in senses.items():
        if name not in values:
            continue
        lo = float(nadir[name])
        hi = float(ideal[name])
        span = hi - lo
        raw = float(values[name])
        if abs(span) < 1e-12:
            out[name] = 1.0
            continue
        if sense == "max":
            # nadir worse/smaller → ideal better/larger
            out[name] = (raw - lo) / (hi - lo)
        else:
            # nadir worse/larger → ideal better/smaller
            out[name] = (lo - raw) / (lo - hi)
        out[name] = min(1.0, max(0.0, out[name]))
    return out


def _nondominated_max_tuples(points: list[tuple[float, ...]]) -> list[tuple[float, ...]]:
    kept: list[tuple[float, ...]] = []
    for cand in points:
        if any(
            all(o >= c for o, c in zip(other, cand, strict=True))
            and any(o > c for o, c in zip(other, cand, strict=True))
            for other in points
            if other is not cand
        ):
            continue
        if cand not in kept:
            kept.append(cand)
    return kept


def hypervolume_maximization(
    points: Sequence[Mapping[str, float]],
    *,
    reference: Mapping[str, float],
    objectives: Sequence[str],
) -> float:
    """Exact hypervolume for maximization-form vectors (higher is better).

    Reference must be componentwise strictly worse than contributing points.
    """
    if not points or not objectives:
        return 0.0
    ref_t = tuple(float(reference[o]) for o in objectives)
    pts = [
        tuple(float(p[o]) for o in objectives)
        for p in points
        if all(float(p[o]) > float(reference[o]) for o in objectives)
    ]
    pts = _nondominated_max_tuples(pts)
    return _hv_exact(pts, ref_t)


def _hv_exact(points: list[tuple[float, ...]], ref: tuple[float, ...]) -> float:
    if not points:
        return 0.0
    dim = len(ref)
    if dim == 1:
        return max(0.0, max(p[0] for p in points) - ref[0])

    ordered = sorted(points, key=lambda p: p[-1])
    volume = 0.0
    for i, point in enumerate(ordered):
        prev = ref[-1] if i == 0 else ordered[i - 1][-1]
        height = point[-1] - prev
        if height <= 0:
            continue
        slice_pts = [q[:-1] for q in ordered[i:]]
        slice_pts = _nondominated_max_tuples(slice_pts)
        volume += height * _hv_exact(slice_pts, ref[:-1])
    return volume


def payoff_ranges_from_matrix(
    matrix: Sequence[Mapping[str, int | float]],
    *,
    objectives: Sequence[str],
    senses: Mapping[str, str] | None = None,
) -> tuple[dict[str, float], dict[str, float]]:
    """Ideal = best per column; nadir ≈ worst per column across payoff rows."""
    sense_map = senses or OBJECTIVE_SENSES
    ideal: dict[str, float] = {}
    nadir: dict[str, float] = {}
    for name in objectives:
        col = [float(row[name]) for row in matrix if name in row]
        if not col:
            raise ValueError(f"payoff matrix missing objective {name}")
        if sense_map[name] == "max":
            ideal[name] = max(col)
            nadir[name] = min(col)
        else:
            ideal[name] = min(col)
            nadir[name] = max(col)
    return ideal, nadir


def build_epsilon_levels(
    *,
    ideal: float,
    nadir: float,
    levels: int,
    sense: str,
) -> list[int]:
    """N direction-aware epsilon bounds from loose → tight."""
    if levels < 2:
        raise ValueError("levels must be >= 2")
    if sense == "max":
        # lower bounds: nadir (loose) → ideal (tight)
        raw = [nadir + (ideal - nadir) * i / (levels - 1) for i in range(levels)]
    else:
        # upper bounds: nadir/worse large (loose) → ideal/small (tight)
        raw = [nadir + (ideal - nadir) * i / (levels - 1) for i in range(levels)]
    return sorted({int(round(v)) for v in raw})


def generate_epsilon_grid(
    *,
    ideal: Mapping[str, float],
    nadir: Mapping[str, float],
    grid_objectives: Sequence[str],
    levels: int = 3,
    senses: Mapping[str, str] | None = None,
) -> list[dict[str, int]]:
    sense_map = senses or OBJECTIVE_SENSES
    axes: list[list[int]] = []
    names: list[str] = []
    for name in grid_objectives:
        vals = build_epsilon_levels(
            ideal=float(ideal[name]),
            nadir=float(nadir[name]),
            levels=levels,
            sense=sense_map[name],
        )
        # ensure at least ``levels`` unique when span collapses
        if len(vals) < levels:
            vals = sorted({int(round(ideal[name])), int(round(nadir[name]))} | set(vals))
        names.append(name)
        axes.append(vals)
    grid: list[dict[str, int]] = []
    for combo in itertools.product(*axes):
        grid.append(dict(zip(names, combo, strict=True)))
    return grid


def single_objective_weights(
    name: str, objectives: Sequence[str] = DEFAULT_OBJECTIVES
) -> dict[str, float]:
    return {obj: (1.0 if obj == name else 0.0) for obj in objectives}


SolveFn = Callable[..., dict[str, Any]]


def run_payoff_table(
    solve: SolveFn,
    *,
    objectives: Sequence[str] = DEFAULT_OBJECTIVES,
    split: str | None = "calib",
    persist: bool = False,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    points: list[ObjectivePoint] = []
    for name in objectives:
        result = solve(
            persist=persist,
            split=split,
            objective_mode="weighted_sum",
            lambda_weights=single_objective_weights(name, objectives),
        )
        values = dict((result.get("multiobjective") or {}).get("values") or {})
        point = ObjectivePoint(
            values={k: int(values.get(k, 0)) for k in objectives},
            source=f"payoff:{name}",
            status=str(result.get("solver_status", "UNKNOWN")),
            wall_time_seconds=float(
                ((result.get("multiobjective") or {}).get("wall_time_seconds")) or 0.0
            ),
            extras={"assigned": result.get("assigned"), "optimized": name},
        )
        points.append(point)
        rows.append(point.as_dict())

    matrix = [p.values for p in points]
    ideal, nadir = payoff_ranges_from_matrix(matrix, objectives=objectives)
    return {
        "objectives": list(objectives),
        "senses": {o: OBJECTIVE_SENSES[o] for o in objectives},
        "rows": rows,
        "ideal": ideal,
        "nadir": nadir,
    }


def run_epsilon_grid_scan(
    solve: SolveFn,
    *,
    payoff: Mapping[str, Any],
    primary: str = DEFAULT_PRIMARY,
    grid_objectives: Sequence[str] = DEFAULT_GRID_OBJECTIVES,
    levels: int = 3,
    split: str | None = "calib",
    persist: bool = False,
    max_points: int | None = None,
    progress: Callable[[int, int, dict[str, int]], None] | None = None,
) -> dict[str, Any]:
    ideal = dict(payoff["ideal"])
    nadir = dict(payoff["nadir"])
    objectives = list(payoff.get("objectives") or DEFAULT_OBJECTIVES)
    grid = generate_epsilon_grid(
        ideal=ideal,
        nadir=nadir,
        grid_objectives=grid_objectives,
        levels=levels,
    )
    if max_points is not None:
        grid = grid[: max(0, int(max_points))]

    points: list[ObjectivePoint] = []
    for idx, bounds in enumerate(grid, start=1):
        if progress:
            progress(idx, len(grid), bounds)
        values: dict[str, int] = {}
        wall = 0.0
        assigned = None
        err = None
        try:
            result = solve(
                persist=persist,
                split=split,
                objective_mode="epsilon_constraint",
                epsilon_primary=primary,
                epsilon_bounds=bounds,
            )
            status = str(result.get("solver_status", "UNKNOWN"))
            values = {
                k: int(v)
                for k, v in dict(
                    (result.get("multiobjective") or {}).get("values") or {}
                ).items()
            }
            wall = float(
                ((result.get("multiobjective") or {}).get("wall_time_seconds")) or 0.0
            )
            assigned = result.get("assigned")
        except Exception as exc:  # noqa: BLE001 — record infeasible / solver errors
            status = f"ERROR:{type(exc).__name__}"
            err = str(exc)

        point = ObjectivePoint(
            values={k: int(values.get(k, 0)) for k in objectives} if values else {},
            source=f"epsilon:{idx}",
            status=status,
            wall_time_seconds=wall,
            extras={
                "epsilon_bounds": dict(bounds),
                "assigned": assigned,
                "error": err,
            },
        )
        points.append(point)

    feasible = [p for p in points if p.values and p.status in ("OPTIMAL", "FEASIBLE")]
    front = filter_nondominated(feasible)
    senses = {o: OBJECTIVE_SENSES[o] for o in objectives}
    norm_points = [
        normalize_for_maximization(p.values, ideal=ideal, nadir=nadir, senses=senses)
        for p in front
    ]
    ref = {o: -0.05 for o in objectives}
    hv = hypervolume_maximization(norm_points, reference=ref, objectives=list(objectives))

    return {
        "primary": primary,
        "grid_objectives": list(grid_objectives),
        "levels": levels,
        "n_grid": len(grid),
        "n_feasible": len(feasible),
        "n_nondominated": len(front),
        "hypervolume": round(hv, 6),
        "grid": grid,
        "points": [p.as_dict() for p in points],
        "front": [p.as_dict() for p in front],
    }


def run_baselines(
    solve: SolveFn,
    *,
    objectives: Sequence[str] = DEFAULT_OBJECTIVES,
    split: str | None = "calib",
    persist: bool = False,
) -> list[dict[str, Any]]:
    specs: list[tuple[str, dict[str, Any]]] = [
        ("weighted_sum", {"objective_mode": "weighted_sum"}),
        (
            "lexicographic",
            {
                "objective_mode": "lexicographic",
                "objective_order": list(objectives),
            },
        ),
    ]
    out: list[dict[str, Any]] = []
    for label, kwargs in specs:
        try:
            result = solve(persist=persist, split=split, **kwargs)
            values = dict((result.get("multiobjective") or {}).get("values") or {})
            out.append(
                {
                    "label": label,
                    "status": result.get("solver_status"),
                    "assigned": result.get("assigned"),
                    "values": {k: int(values.get(k, 0)) for k in objectives},
                    "wall_time_seconds": float(
                        ((result.get("multiobjective") or {}).get("wall_time_seconds"))
                        or 0.0
                    ),
                    "exact_hierarchy": (
                        (result.get("multiobjective") or {}).get("exact_hierarchy")
                    ),
                }
            )
        except Exception as exc:  # noqa: BLE001
            out.append(
                {
                    "label": label,
                    "status": f"ERROR:{type(exc).__name__}",
                    "assigned": None,
                    "values": {},
                    "wall_time_seconds": 0.0,
                    "exact_hierarchy": None,
                    "error": str(exc),
                }
            )
    return out


def write_phase3_reports(
    *,
    payoff: Mapping[str, Any],
    scan: Mapping[str, Any],
    baselines: Sequence[Mapping[str, Any]],
    out_dir: Path | None = None,
    stamp: str | None = None,
) -> dict[str, str]:
    directory = out_dir or REPORT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    ts = stamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "payoff_ideal": payoff.get("ideal"),
        "payoff_nadir": payoff.get("nadir"),
        "scan": {
            "primary": scan.get("primary"),
            "grid_objectives": scan.get("grid_objectives"),
            "levels": scan.get("levels"),
            "n_grid": scan.get("n_grid"),
            "n_feasible": scan.get("n_feasible"),
            "n_nondominated": scan.get("n_nondominated"),
            "hypervolume": scan.get("hypervolume"),
        },
        "baselines": list(baselines),
        "front": scan.get("front"),
    }
    paths = {
        "payoff": str(directory / f"payoff_{ts}.json"),
        "summary": str(directory / f"summary_{ts}.json"),
        "grid_csv": str(directory / f"epsilon_grid_{ts}.csv"),
        "latest_summary": str(directory / "summary_latest.json"),
    }
    Path(paths["payoff"]).write_text(
        json.dumps(payoff, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    Path(paths["summary"]).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    Path(paths["latest_summary"]).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    objectives = list(payoff.get("objectives") or DEFAULT_OBJECTIVES)
    fieldnames = [
        "index",
        "status",
        "wall_time_seconds",
        *objectives,
        *[f"eps_{g}" for g in (scan.get("grid_objectives") or [])],
    ]
    with Path(paths["grid_csv"]).open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for i, point in enumerate(scan.get("points") or [], start=1):
            row: dict[str, Any] = {
                "index": i,
                "status": point.get("status"),
                "wall_time_seconds": point.get("wall_time_seconds"),
            }
            for o in objectives:
                row[o] = (point.get("values") or {}).get(o, "")
            bounds = ((point.get("extras") or {}).get("epsilon_bounds")) or {}
            for g in scan.get("grid_objectives") or []:
                row[f"eps_{g}"] = bounds.get(g, "")
            writer.writerow(row)
    return paths
