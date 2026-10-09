"""CLI: SOFA vs GBDT priority ablation."""

from __future__ import annotations

import json

from domain.scoring.priority_ablation import run_priority_ablation


def main() -> None:
    print(json.dumps(run_priority_ablation(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
