"""Unit tests for S3 multi-episode fair benchmark helpers (no PPO / no DB)."""

from __future__ import annotations

import json

from application.h3_ui import benchmark_summary_rows, load_benchmark
from domain.ops.h3_benchmark import summarize_benchmark_episodes


def test_summarize_benchmark_episodes_means():
    episodes = [
        {
            "episode": 1,
            "ppo": {
                "assigned": 4,
                "total_reward": 10.0,
                "high_risk_wait": 2,
                "constraint_violations": 0,
            },
            "greedy": {
                "assigned": 4,
                "total_reward": 9.0,
                "high_risk_wait": 3,
                "constraint_violations": 1,
            },
            "cp_sat": {
                "assigned": 4,
                "evaluation": {"high_risk_wait": 1, "constraint_violations": 0},
            },
        },
        {
            "episode": 2,
            "ppo": {
                "assigned": 6,
                "total_reward": 14.0,
                "high_risk_wait": 0,
                "constraint_violations": 0,
            },
            "greedy": {
                "assigned": 5,
                "total_reward": 11.0,
                "high_risk_wait": 1,
                "constraint_violations": 0,
            },
            "cp_sat": {
                "assigned": 6,
                "evaluation": {"high_risk_wait": 0, "constraint_violations": 0},
            },
        },
    ]
    summary = summarize_benchmark_episodes(
        episodes,
        episodes=2,
        seed=42,
        candidate_patients=20,
        pool_patients=200,
        model_path="artifacts/ppo_icu",
    )
    assert summary["fair_pool"] is True
    assert summary["ppo"]["mean_assigned"] == 5.0
    assert summary["greedy"]["mean_high_risk_wait"] == 2.0
    assert summary["cp_sat"]["mean_assigned"] == 5.0
    assert "Offline only" in summary["note"]


def test_load_benchmark_and_rows(tmp_path):
    missing = load_benchmark(tmp_path)
    assert missing["status"] == "missing"

    reports = tmp_path / "reports"
    reports.mkdir()
    payload = {
        "status": "ok",
        "fair_pool": True,
        "summary": {
            "episodes": 2,
            "ppo": {"mean_assigned": 4.0, "mean_high_risk_wait": 1.0},
            "greedy": {"mean_assigned": 4.0},
            "cp_sat": {"mean_assigned": 4.0, "mean_constraint_violations": 0.0},
            "note": "fair",
        },
    }
    (reports / "ppo_benchmark.json").write_text(json.dumps(payload), encoding="utf-8")
    loaded = load_benchmark(tmp_path)
    assert loaded["status"] == "ok"
    rows = benchmark_summary_rows(loaded["payload"])
    assert len(rows) == 3
    assert rows[0]["policy"] == "ppo"
    assert rows[0]["mean_assigned"] == 4.0
