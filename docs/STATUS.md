# 项目状态

> 更新：2026-07-27 · Owner 数据底座

## 数据

| 项 | 状态 |
|----|------|
| Layer0 labevents | ✅ 158,374,764 |
| feat.sofa_timeseries | ✅ 94458 |
| dump | ✅ `dumps/icu_scheduling_P0-full_mimic_94458stays_20260727.dump` |
| simulate | 见下方 |

## simulate 结果

```
{
  "sofa_rows": 94458,
  "eval_split": {
    "seed": 42,
    "calib_ratio": 0.7,
    "n_calib": 66121,
    "n_eval": 28337,
    "note": "Wave1 skeleton: assignment still uses full cohort; Wave2 B should restrict calib/eval runs"
  },
  "run_id": "p0_daf0724e",
  "assigned": 20,
  "n_beds": 20,
  "n_stays": 94458,
  "n_candidates": 200,
  "solver_status": "OPTIMAL",
  "metrics": {
    "n_stays": 94458,
    "n_beds": 20,
    "assigned": 20,
    "unassigned": 94438,
    "solver_status": "OPTIMAL"
  },
  "status": "simulate_ok"
}

```

## 说明

- CP-SAT P0 使用 top-200 候选（`configs/optimizer.yaml` `solver.candidate_cap`）；全量 94k×床不可在 30–60s 内求解
- dump/artifact **不入 GitHub**；请线下分发
- Draft PR #3 PPO 仍保持 Draft

进度看板：`d:\project\_local-data\mimic\PROGRESS.md`
