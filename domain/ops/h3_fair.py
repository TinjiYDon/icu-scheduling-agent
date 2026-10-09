"""Fair H3 helpers: same stay pool for PPO / greedy / CP-SAT."""

from __future__ import annotations

from typing import Any, Sequence


def stay_ids_from_env(env: Any) -> list[int]:
    return [int(p.stay_id) for p in list(getattr(env, "patients", []) or [])]


def fair_pool_note(n_stays: int, n_beds: int) -> str:
    return (
        f"Fair H3: PPO / greedy / CP-SAT share the same {n_stays} stay_ids "
        f"and {n_beds} beds. Offline only — do not claim online MIMIC-PPO."
    )


def resource_overrides_from_env(env: Any) -> dict[str, Any]:
    """Copy isolation / vent / zone layout from the PPO env into CP-SAT overrides."""
    beds = list(getattr(env, "beds", []) or [])
    n_beds = len(beds)
    n_iso = sum(1 for b in beds if bool(getattr(b, "is_isolation", False)))
    n_vent = getattr(env, "ventilator_capacity", None)
    if n_vent is None:
        n_vent = sum(1 for b in beds if bool(getattr(b, "has_ventilator", False)))
    bed_zones: list[list[Any]] = []
    if beds:
        start = int(beds[0].bed_id)
        count = 0
        label = str(getattr(beds[0], "zone", "REG") or "REG")
        prev_id = start - 1
        for bed in beds:
            bid = int(bed.bed_id)
            zone = str(getattr(bed, "zone", "REG") or "REG")
            if zone == label and bid == prev_id + 1:
                count += 1
            else:
                bed_zones.append([start, count, label])
                start = bid
                count = 1
                label = zone
            prev_id = bid
        bed_zones.append([start, count, label])
    return {
        "n_beds": n_beds,
        "n_isolation_beds": int(n_iso),
        "n_ventilators": int(n_vent),
        "bed_zones": bed_zones,
    }


def annotate_fair_report(
    report: dict[str, Any],
    *,
    stay_ids: Sequence[int],
    n_beds: int,
    resources: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = dict(report)
    out["fair_pool"] = True
    out["shared_stay_ids"] = [int(x) for x in stay_ids]
    out["shared_n_beds"] = int(n_beds)
    if resources is not None:
        out["shared_resources"] = dict(resources)
    out["note"] = fair_pool_note(len(stay_ids), int(n_beds))
    return out
