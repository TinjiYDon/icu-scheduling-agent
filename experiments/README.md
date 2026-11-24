# Independent scheduling experiment snapshot

This directory belongs only to `icu-scheduling-agent` and runs without the sibling repository.
The original shared workspace experiment sources have been copied locally, not linked.

## Scope and status

Archived November B0–B7 / LARE comparisons (decision) or eight-policy simulator (scheduling), as applicable to this repository only. These are existing experimental algorithms, not newly completed V3 work.
Decision results retain historical 70/10/20 splits and charttime-based availability; they are NOT causally sealed V3 60/20/20 results. Scheduling archives may contain multiple method subsets: use the methods and n_runs recorded in each JSON, not a blanket eight-method claim.

## Reproduction

Use this repository's Python environment from the repository root. Set MIMIC_DSN and the project-specific ICU_DECISION_DSN or ICU_SCHEDULING_DSN. Set MIMIC_CSV_ROOT to the licensed MIMIC CSV directory for ETL. No credentials are committed.

Data preparation uses only MIMIC_DSN and ICU_SCHEDULING_DSN; no decision database or sibling repository is required.

Run `python experiments/scheduling/src/build_scenario.py`, then `python experiments/scheduling/src/run_bench.py --all`, then `aggregate.py` and `verify.py` in the same src directory. Scenario data and patient trajectories are local only. The simulator is a separate experimental implementation, not a replacement for the application default CP-SAT.

## Published material

Only source, historical aggregate tables, reports and figures are included. Patient-level data, predictions, split IDs and trajectories are excluded. Original RUNLOG/SECTION text is retained as historical evidence; this README controls current release claims.
