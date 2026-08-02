# 项目状态

> 更新：2026-08-02 · **滚动时域实时调度**主叙事 · Wave2 SOFA simulate 数值保留

## 数据

| 项 | 状态 |
|----|------|
| Layer0 labevents | ✅ 158,374,764 |
| feat.sofa_timeseries | ✅ 94,458（真实 SOFA · 0~12 · avg 4.74）|
| dump | ✅ `dumps/icu_scheduling_P0-full_mimic_94458stays_20260802.dump` · 见 [`DUMP_READY.md`](DUMP_READY.md) |
| 交互台 | ✅ Streamlit：CP-SAT + 滚动时间线 + 验收门禁 |
| 下一步 | [`TOP_TIER_NEXT.md`](TOP_TIER_NEXT.md) |
| 交付说明 | [`DUMP_READY.md`](DUMP_READY.md) |
| simulate | ✅ OPTIMAL · **n_candidates=1000** · assigned=20 |

## 仿真指标（Wave2 · 真实 SOFA · 2026-07-31）

> `python -m application.simulate` · status=simulate_ok

| 指标 | 值 |
|------|----|
| 仿真时长 | 24 h（12 步 × 2 h）|
| 出院 / 入院 | 34 / 49 |
| 最终占用 | 20 / 20 床（利用率 100%）|
| 候选患者 avg_sofa | 11.8（危重优先，非全库均值）|
| 平均权重 | 2.19 |

## 调参 / 可视化

| 项 | 入口 |
|----|------|
| Streamlit | `streamlit run presentation/streamlit_app.py` |
| MLflow | `mlflow ui --backend-store-uri sqlite:///./mlflow.db` |
| 说明 | [`TUNING_LOCAL.md`](TUNING_LOCAL.md) |
| PPO smoke | [`PPO_SMOKE.md`](PPO_SMOKE.md) · 代码在 main · **默认 cp_sat** · 无 MIMIC 轨迹 |

## 说明

- `candidate_cap` 只限制 CP-SAT 候选，**不**裁剪 labs/SOFA/feat
- **dump 可支撑** CP-SAT/仿真；**不可**单独支撑 online PPO 轨迹
- PR #3 已于 2026-07-30 合入 main；`policy.default` 仍为 `cp_sat`
- GitHub（2026-08-02）：无 open PR；轨迹仍缺
- 进度看板：`d:\project\_local-data\mimic\PROGRESS.md`
