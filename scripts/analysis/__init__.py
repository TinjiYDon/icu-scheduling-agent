"""Reproducible analysis helpers for the rolling-Pareto evidence trail.

Each module is a standalone CLI.  They read the artefacts produced by
``application.run_timed_pareto`` (``reports/rolling/*.json``) plus the local SOFA
sample (``artifacts/sofa_sample/sofa_sample.json``), and print tables that back
the claims recorded in ``MULTIOBJECTIVE_TASKS.md``.

| module | question it answers |
|---|---|
| ``replay_summary`` | per-step objectives, transfer gate, front size |
| ``move_stability_probe`` | is there a stability/yield curve? does f5 buy f4? |
| ``transfer_pool_effect`` | is the transfer gain real or a candidate-pool artefact? |
| ``mimic_date_shift_check`` | why calendar dates cannot drive the clock |
"""
