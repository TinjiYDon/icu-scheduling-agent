"""Scale ICU bed layout with n_beds for consistent CP-SAT / rolling demos."""

from __future__ import annotations


_DEFAULT_SHARE = (
    ("ISO", 4),
    ("MICU", 4),
    ("SICU", 4),
    ("CCU", 4),
    ("NICU", 4),
)
_DEFAULT_TOTAL = sum(c for _, c in _DEFAULT_SHARE)  # 20


def scale_bed_layout(n_beds: int) -> dict:
    """Return resources fields scaled from the default 20-bed ward template.

    Isolation / zone counts keep approximate proportions of the 20-bed layout.
    Remainder beds are appended to the last zone so the total equals n_beds.
    """
    n = int(n_beds)
    if n < 1:
        raise ValueError("n_beds must be >= 1")

    if n < len(_DEFAULT_SHARE):
        # Tiny wards: first bed ISO if possible, rest REG-labeled as MICU…
        labels = [lab for lab, _ in _DEFAULT_SHARE]
        counts = [0] * len(labels)
        for i in range(n):
            counts[min(i, len(labels) - 1)] += 1
    else:
        counts = [max(1, round(n * share / _DEFAULT_TOTAL)) for _, share in _DEFAULT_SHARE]
        diff = n - sum(counts)
        counts[-1] += diff
        # Keep non-negative / at least 0; repair if over-corrected
        while counts[-1] < 0:
            for i in range(len(counts) - 1):
                if counts[i] > 1:
                    counts[i] -= 1
                    counts[-1] += 1
                    break
            else:
                break

    bed_zones: list[list] = []
    start = 1
    for (label, _), count in zip(_DEFAULT_SHARE, counts):
        if count <= 0:
            continue
        bed_zones.append([start, int(count), label])
        start += int(count)

    n_iso = int(bed_zones[0][1]) if bed_zones and bed_zones[0][2] == "ISO" else max(1, n // 5)
    n_vents = max(1, round(n * 8 / _DEFAULT_TOTAL))
    max_patients = max(n * 10, 50)

    return {
        "n_beds": n,
        "n_isolation_beds": n_iso,
        "n_ventilators": n_vents,
        "max_patients": max_patients,
        "bed_zones": bed_zones,
    }


def layout_covers_beds(bed_zones: list, n_beds: int) -> bool:
    """True if configured zones cover bed ids 1..n_beds exactly once."""
    if not bed_zones:
        return False
    covered: set[int] = set()
    for start, count, _label in bed_zones:
        for b in range(int(start), int(start) + int(count)):
            covered.add(b)
    return covered == set(range(1, int(n_beds) + 1))
