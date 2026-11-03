"""One-shot local check for icu-scheduling-agent."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = Path.home() / ".dsh" / "skills" / "complex-project-harness" / "scripts" / "preflight.py"
TESTS = [
    "tests/test_data_contract.py",
    "tests/test_fd_stress.py",
    "tests/test_pool_effect.py",
    "tests/test_aigc_grid.py",
    "tests/test_pareto_decision.py",
    "tests/test_pareto_io.py",
]


def run(cmd: list[str]) -> int:
    print("+", " ".join(cmd))
    return subprocess.run(cmd, cwd=str(ROOT)).returncode


def main() -> int:
    code = run([sys.executable, str(PREFLIGHT), "--config", str(ROOT / "preflight.yaml")])
    if code:
        print("PREFLIGHT FAILED")
        return code
    return run([sys.executable, "-m", "pytest", *TESTS, "-q"])


if __name__ == "__main__":
    raise SystemExit(main())
