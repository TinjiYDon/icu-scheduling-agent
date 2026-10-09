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


def annotate_fair_report(
    report: dict[str, Any],
    *,
    stay_ids: Sequence[int],
    n_beds: int,
) -> dict[str, Any]:
    out = dict(report)
    out["fair_pool"] = True
    out["shared_stay_ids"] = [int(x) for x in stay_ids]
    out["shared_n_beds"] = int(n_beds)
    out["note"] = fair_pool_note(len(stay_ids), int(n_beds))
    return out
