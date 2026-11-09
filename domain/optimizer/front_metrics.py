"""Front quality metrics for the epsilon scan: nondominance, HV and knee point.

All helpers are pure and DB-free.  Objective vectors are handled in
*maximization* form, i.e. every component has been flipped so that larger is
better.  Use :func:`normalize_to_max` to move raw objective values into that
space with a shared ideal/nadir, which keeps HV comparable across runs.

Why this module exists
----------------------
``timed_pareto`` can already filter a sampled front, but it cannot answer
"how much of the objective space does this front cover" (HV) or "which single
point is the balanced compromise" (knee).  Both are needed before the scan
quality can be reported, and both must use one shared normalisation so that two
scans are actually comparable.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

# Neutral reference used after normalisation: slightly worse than any feasible
# normalised value so that every point contributes volume.
DEFAULT_REFERENCE = -0.05

# A knee is only reported when the front bulges away from the chord by at least
# this fraction of the chord length.  Near-collinear fronts -- the norm for an
# epsilon sweep where each extra unit of epsilon buys a constant amount of the
# pivot -- have no meaningful knee, and reporting one would describe the
# sampling spacing rather than the instance.
KNEE_MIN_PROMINENCE = 0.02


def dominates(a: Sequence[float], b: Sequence[float]) -> bool:
    """True if ``a`` Pareto-dominates ``b`` (maximisation form)."""
    better = False
    for av, bv in zip(a, b, strict=True):
        if av < bv:
            return False
        if av > bv:
            better = True
    return better


def nondominated(points: Sequence[Sequence[float]]) -> list[Sequence[float]]:
    """Keep points not dominated by any other, preserving input order."""
    kept: list[Sequence[float]] = []
    for i, cand in enumerate(points):
        if any(
            dominates(other, cand)
            for j, other in enumerate(points)
            if i != j
        ):
            continue
        if not any(all(x == y for x, y in zip(cand, kept_p, strict=True)) for kept_p in kept):
            kept.append(cand)
    return kept


def normalize_to_max(
    values: Mapping[str, float],
    *,
    ideal: Mapping[str, float],
    nadir: Mapping[str, float],
    senses: Mapping[str, str],
) -> dict[str, float]:
    """Map each objective to [0, 1] where 1 is best, flipping minimised ones."""
    out: dict[str, float] = {}
    for name, sense in senses.items():
        if name not in values or name not in ideal or name not in nadir:
            continue
        best = float(ideal[name])
        worst = float(nadir[name])
        raw = float(values[name])
        if abs(best - worst) < 1e-12:
            out[name] = 1.0
            continue
        # 1.0 means "as good as the ideal" for both senses.
        if sense == "max":
            score = (raw - worst) / (best - worst)
        else:
            score = (worst - raw) / (worst - best)
        out[name] = min(1.0, max(0.0, score))
    return out


def _nondominated_tuples(points: Sequence[Sequence[float]]) -> list[tuple[float, ...]]:
    return [tuple(p) for p in nondominated(points)]


def _hv_exact(
    points: Sequence[tuple[float, ...]], ref: tuple[float, ...]
) -> float:
    """Exact hypervolume by recursive slicing along the last coordinate."""
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
        slice_pts = _nondominated_tuples([q[:-1] for q in ordered[i:]])
        volume += height * _hv_exact(slice_pts, ref[:-1])
    return volume


def hypervolume(
    points: Iterable[Mapping[str, float] | Sequence[float]],
    *,
    objectives: Sequence[str] | None = None,
    reference: float | Mapping[str, float] = DEFAULT_REFERENCE,
) -> float:
    """Exact hypervolume of ``points`` in maximisation form.

    ``points`` may be mappings (then ``objectives`` selects and orders the
    columns) or plain sequences.  Points not strictly better than ``reference``
    in every coordinate are dropped, as they contribute no volume.
    """
    rows = list(points)
    if not rows:
        return 0.0

    if isinstance(rows[0], Mapping):
        if not objectives:
            raise ValueError("objectives are required for mapping points")
        names = list(objectives)
        ref_t = tuple(
            float(reference[n]) if isinstance(reference, Mapping) else float(reference)
            for n in names
        )
        tuples = [tuple(float(p[n]) for n in names) for p in rows]  # type: ignore[index]
    else:
        names = []
        dim = len(rows[0])  # type: ignore[arg-type]
        ref_t = (float(reference),) * dim if not isinstance(reference, Mapping) else ()
        if isinstance(reference, Mapping):
            raise ValueError("objectives are required for mapping references")
        tuples = [tuple(float(v) for v in p) for p in rows]  # type: ignore[union-attr]

    contributing = [p for p in tuples if all(v > r for v, r in zip(p, ref_t, strict=True))]
    if not contributing:
        return 0.0
    return _hv_exact(_nondominated_tuples(contributing), ref_t)


def knee_analysis(
    points: Sequence[Mapping[str, float] | Sequence[float]],
    *,
    objectives: Sequence[str] | None = None,
    min_prominence: float = KNEE_MIN_PROMINENCE,
    axes: Sequence[Any] | None = None,
    pivot: Any | None = None,
) -> dict[str, Any]:
    """Locate the knee and report how pronounced it is.

    The knee is the point farthest (in the chosen 2-D plane) from the chord
    joining the two extremes of the front, where "extremes" are the points with
    the minimum and maximum value on the plane's *first* axis.  Using the axis
    range to define the endpoints is what keeps the chord well conditioned: a
    lexicographic ``argmax`` on both axes can return two nearly identical points,
    collapsing the chord to near-zero length and inflating every distance by
    orders of magnitude.

    ``prominence`` is the winning perpendicular distance divided by the chord
    length, so it is scale free and comparable across instances.  A front that
    is (near-)collinear has ``prominence ~ 0`` and **no meaningful knee**; in
    that case ``index`` is ``None`` and ``distinct`` is ``False``.  This matters
    for epsilon sweeps: when every extra unit of epsilon buys a constant amount
    of the pivot the front is a straight line, and any point picked by the
    geometric rule would be an artefact of the sampling spacing rather than a
    property of the instance.

    The knee is inherently a 2-D notion, so with three or more objectives the
    plane must be chosen.  Pass ``axes=(a, b)`` to fix it explicitly, or
    ``pivot=a`` to force ``a`` to be the first axis and let the axis with the
    largest spread among the rest be the second.  With neither, the two
    highest-spread axes are used.  ``axes`` in the result reports the choice.

    Returns ``{"index", "prominence", "distinct", "egalitarian_index", "axes"}``;
    ``index`` is ``None`` when there are fewer than three points, no axis has
    spread, or the bulge is below ``min_prominence``.
    """
    flat = {
        "index": None,
        "prominence": 0.0,
        "distinct": False,
        "egalitarian_index": None,
        "axes": None,
    }
    rows = list(points)
    if len(rows) < 3:
        return flat
    if isinstance(rows[0], Mapping):
        if not objectives:
            raise ValueError("objectives are required for mapping points")
        names = list(objectives)
        mat = [[float(p[n]) for n in names] for p in rows]  # type: ignore[index]
    else:
        names = []
        mat = [[float(v) for v in p] for p in rows]  # type: ignore[union-attr]
    columns = len(mat[0]) if mat else 0
    if columns < 2:
        return flat

    def _col(key: Any) -> int:
        if names:
            if key not in names:
                raise ValueError(f"unknown knee axis {key!r}; have {names}")
            return names.index(key)
        return int(key)

    ranges = [max(col) - min(col) for col in zip(*mat, strict=True)]
    if axes is not None:
        if len(axes) != 2:
            raise ValueError("axes must contain exactly two objectives")
        i0, i1 = _col(axes[0]), _col(axes[1])
    elif pivot is not None:
        i0 = _col(pivot)
        others = [i for i in range(columns) if i != i0]
        i1 = max(others, key=lambda i: ranges[i])
    else:
        ordered = sorted(range(columns), key=lambda i: ranges[i], reverse=True)
        i0, i1 = ordered[0], ordered[1]
    if ranges[i0] < 1e-12 or ranges[i1] < 1e-12:
        return flat
    axes_used = (names[i0], names[i1]) if names else (i0, i1)

    # Endpoints come from the first axis' own range, so they are distinct by
    # construction and the chord always spans the full extent of that axis.
    start = min(range(len(mat)), key=lambda i: mat[i][i0])
    end = max(range(len(mat)), key=lambda i: mat[i][i0])
    # Distance is measured in the same 2-D plane as the chord.  Measuring in the
    # full space while the chord lives on two axes mixes two geometries: a short
    # chord plus a third axis with any spread produces "distances" several times
    # the chord length, and the point then gets chosen by the ignored axes rather
    # than by the trade-off actually being traced.
    a = (mat[start][i0], mat[start][i1])
    b = (mat[end][i0], mat[end][i1])
    direction = (b[0] - a[0], b[1] - a[1])
    norm = math.hypot(direction[0], direction[1])
    if norm < 1e-12:
        return flat
    unit = (direction[0] / norm, direction[1] / norm)

    best_idx, best_dist = None, -1.0
    for idx, row in enumerate(mat):
        if idx in (start, end):
            continue
        rel = (row[i0] - a[0], row[i1] - a[1])
        proj = rel[0] * unit[0] + rel[1] * unit[1]
        dist = math.hypot(rel[0] - proj * unit[0], rel[1] - proj * unit[1])
        if dist > best_dist:
            best_idx, best_dist = idx, dist

    prominence = max(0.0, best_dist) / norm
    # The most defensible reading of "most balanced" when the geometric rule has
    # nothing to say: maximise the worst normalised objective (max-min fairness).
    egalitarian = max(range(len(mat)), key=lambda i: min(mat[i]))
    if best_idx is None or best_dist < 1e-12:
        # Exactly flat against the chord: no point bulges, so no knee exists.
        return {
            "index": None,
            "prominence": round(prominence, 8),
            "distinct": False,
            "egalitarian_index": egalitarian,
            "axes": axes_used,
        }
    if prominence < min_prominence:
        return {
            "index": None,
            "prominence": round(prominence, 8),
            "distinct": False,
            "egalitarian_index": egalitarian,
            "axes": axes_used,
        }
    return {
        "index": best_idx,
        "prominence": round(prominence, 8),
        "distinct": True,
        "egalitarian_index": egalitarian,
        "axes": axes_used,
    }


def knee_point(
    points: Sequence[Mapping[str, float] | Sequence[float]],
    *,
    objectives: Sequence[str] | None = None,
    min_prominence: float = 0.0,
    axes: Sequence[Any] | None = None,
    pivot: Any | None = None,
) -> int | None:
    """Index of the most balanced compromise, or ``None`` if there is none.

    Thin wrapper over :func:`knee_analysis`.  It always returns *some* index when
    the front has at least three points and two varying axes: if no bulge is
    found it falls back to the egalitarian (max-min) point.  Use
    :func:`summarize_front` for reporting, which withholds the knee entirely
    when the bulge is below :data:`KNEE_MIN_PROMINENCE`.
    """
    info = knee_analysis(
        points,
        objectives=objectives,
        min_prominence=min_prominence,
        axes=axes,
        pivot=pivot,
    )
    return info["index"] if info["index"] is not None else info["egalitarian_index"]


def summarize_front(
    points: Sequence[Mapping[str, float]],
    *,
    ideal: Mapping[str, float],
    nadir: Mapping[str, float],
    senses: Mapping[str, str],
    reference: float = DEFAULT_REFERENCE,
    min_prominence: float = KNEE_MIN_PROMINENCE,
    knee_pivot: Any | None = None,
    knee_axes: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Normalise, then report front size, hypervolume and the knee point.

    ``knee_pivot`` is forwarded to :func:`knee_analysis`; pass the objective the
    scan is trading away (the pivot) so the knee plane always contains it.
    """
    if not points:
        return {
            "n_front": 0,
            "hypervolume": 0.0,
            "knee_index": None,
            "knee_prominence": 0.0,
            "knee_axes": None,
            "n_knee_ties": 0,
        }
    names = [n for n in senses if n in ideal and n in nadir]
    norm = [
        normalize_to_max(p, ideal=ideal, nadir=nadir, senses=senses) for p in points
    ]
    hv = hypervolume(norm, objectives=names, reference=reference)
    knee = knee_analysis(
        norm,
        objectives=names,
        min_prominence=min_prominence,
        axes=knee_axes,
        pivot=knee_pivot,
    )
    return {
        "n_front": len(points),
        "hypervolume": round(float(hv), 8),
        "knee_index": knee["index"],
        "knee_prominence": knee["prominence"],
        "knee_axes": knee["axes"],
        "n_knee_ties": 0 if knee["index"] is None else 1,
    }
