"""Show why MIMIC calendar dates cannot drive the scheduling clock.

MIMIC shifts dates independently per subject.  Durations inside one stay stay
realistic, but the absolute positions of two different patients are unrelated, so
a concurrent bed-occupancy queue cannot be reconstructed from them.

Run against the local SOFA sample to see the span for yourself:

    python -m scripts.analysis.mimic_date_shift_check
"""

from __future__ import annotations

import argparse
import io
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SAMPLE = ROOT / "artifacts" / "sofa_sample" / "sofa_sample.json"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sample", type=Path, default=DEFAULT_SAMPLE)
    args = p.parse_args()

    payload = json.load(io.open(args.sample, encoding="utf-8"))
    stays = payload["stays"]
    rows = []
    for s in stays:
        tin = datetime.fromisoformat(str(s["intime"]))
        tout = datetime.fromisoformat(str(s["outtime"]))
        rows.append((int(s["stay_id"]), tin, tout, float(s["los"])))
    rows.sort(key=lambda r: r[1])

    print(f"sample                : {args.sample}")
    print(f"stays                 : {len(rows)}")
    print(f"unique subject_id     : {len({s['subject_id'] for s in stays})}")
    print()
    print(f"{'stay_id':>9} {'intime':>20} {'hours':>8} {'los_days':>9}")
    print("-" * 50)
    for sid, tin, tout, los_days in rows[:5]:
        hrs = (tout - tin).total_seconds() / 3600
        print(f"{sid:>9} {tin.isoformat(sep=' '):>20} {hrs:>8.1f} {los_days:>9.2f}")
    print("   ...")
    for sid, tin, tout, los_days in rows[-3:]:
        hrs = (tout - tin).total_seconds() / 3600
        print(f"{sid:>9} {tin.isoformat(sep=' '):>20} {hrs:>8.1f} {los_days:>9.2f}")

    span = rows[-1][1] - rows[0][1]
    print()
    print(f"earliest intime       : {rows[0][1]}")
    print(f"latest   intime       : {rows[-1][1]}")
    print(f"cross-patient span    : {span.days} days ({span.days / 365:.1f} years)")
    print()
    print("Interpretation")
    print("  * per-stay durations (hours / los_days) are realistic;")
    print("  * absolute dates are shifted per subject, so these patients never")
    print("    coexist in wall-clock time -- a real concurrent ICU queue cannot")
    print("    be rebuilt from them.")
    print("  * therefore the replay uses each stay's own relative clinical hour")
    print("    together with a synthetic 2h scheduling clock.")


if __name__ == "__main__":
    main()
