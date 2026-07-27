# 项目状态

> 更新：2026-07-27 · Owner · cap=1000 · Streamlit/MLflow

## 数据

| 项 | 状态 |
|----|------|
| Layer0 labevents | ✅ 158,374,764 |
| feat.sofa_timeseries | ✅ 94,458 |
| dump | ✅ `dumps/icu_scheduling_P0-full_mimic_94458stays_20260727.dump` |
| simulate | ✅ OPTIMAL · **n_candidates=1000** · assigned=20 |

## 调参 / 可视化

| 项 | 入口 |
|----|------|
| Streamlit | `streamlit run presentation/streamlit_app.py` |
| MLflow | `mlflow ui --backend-store-uri sqlite:///./mlflow.db` |
| 说明 | [`TUNING_LOCAL.md`](TUNING_LOCAL.md) |
| PPO smoke（Draft） | [`PPO_SMOKE.md`](PPO_SMOKE.md) · **不合 main** |

## 说明

- `candidate_cap` 只限制 CP-SAT 候选，**不**裁剪 labs/SOFA/feat
- 真 online PPO 轨迹仍归 Draft PR #3 / 成员 B
- 进度看板：`d:\project\_local-data\mimic\PROGRESS.md`
