"""CLI for the small relative-time SOFA/Pareto replay (no database writes).

python -m application.run_timed_pareto --input artifacts/sofa_sample/sofa_sample.json
"""

from domain.rolling.timed_pareto import main

if __name__ == "__main__":
    main()
