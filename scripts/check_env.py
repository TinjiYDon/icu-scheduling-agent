"""Environment check without requiring PostgreSQL or MIMIC."""

from __future__ import annotations

import sys


def main() -> int:
    ok = True
    print(f"Python: {sys.version.split()[0]}")

    try:
        import sqlalchemy

        print(f"SQLAlchemy: {sqlalchemy.__version__}")
    except ImportError:
        print("SQLAlchemy: NOT INSTALLED")
        ok = False

    try:
        from infra.config import load_yaml

        opt = load_yaml("optimizer.yaml")
        print(f"Optimizer beds: {opt.get('resources', {}).get('n_beds')}")
    except Exception as e:
        print(f"Project config: FAIL ({e})")
        ok = False

    try:
        from infra.db import check_connection

        check_connection()
        print("PostgreSQL: CONNECTED")
    except Exception as e:
        print(f"PostgreSQL: NOT READY ({e.__class__.__name__})")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
