# 项目状态

> 更新：2026-08-01 · B 完成 calib/eval split + 业务指标 + λ quick 搜索 + 面板可解释报告 · 2026-07-31 真实 SOFA simulate

## 数据

| 项 | 状态 |
|----|------|
| Layer0 labevents | ✅ 158,374,764 |
| feat.sofa_timeseries | ✅ 94,458（真实 SOFA · 0~12 · avg 4.74）|
| dump | ✅ `dumps/icu_scheduling_P0-full_mimic_94458stays_20260727.dump` · `schemas_only=false` · **已恢复本地** |
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

## CP-SAT 增强（B · 2026-08-01）

- **calib/eval 子集限制**：`run_assignment(split="calib"|"eval")` · 70/30 · seed=42（[`eval_split.py`](`domain/optimizer/eval_split.py`)）
- **业务指标 13 项**：新增 unassigned / high_risk_waiting / avg_assigned_sofa / isolation_utilization / ventilator_utilization
- **可复现**：候选排序加 stay_id tiebreaker；`.gitattributes` 统一 LF
- **可解释报告**：`python -m domain.optimizer.explain [--split ...]` + Streamlit 面板组件化展示

## λ 调参（B · 2026-08-01）

- **quick 16 组 calib 实验完成** → `reports/lambda_tuning_*.csv|json`（不入库）
- 推荐候选：`wait=2.0, overload=0.5, balance=0.1, zone_mismatch=0.5`（**未写回**，待完整 256 组合 + 队友确认）
- 详见 [`LAMBDA_TUNING.md`](LAMBDA_TUNING.md)

## 调参 / 可视化

| 项 | 入口 |
|----|------|
| Streamlit | `streamlit run presentation/streamlit_app.py` |
| MLflow | `mlflow ui --backend-store-uri sqlite:///./mlflow.db` |
| 说明 | [`TUNING_LOCAL.md`](TUNING_LOCAL.md) |
| PPO smoke（Draft） | [`PPO_SMOKE.md`](PPO_SMOKE.md) · **不合 main** |

## 说明

- `candidate_cap` 只限制 CP-SAT 候选，**不**裁剪 labs/SOFA/feat
- **dump 可支撑** CP-SAT/仿真；**不可**单独支撑 online PPO 轨迹
- 真 online PPO 仍归 Draft PR #3 / 成员 B
- GitHub（2026-08-01）：分支 `feat/cp-sat-multi-obj` 已推送全部 B 改动；main 有 Wave2 文档提交
- 进度看板：`d:\project\_local-data\mimic\PROGRESS.md`
