# 项目状态

> 更新：2026-09-24 · **独立调度** · **S2-MOO 阶段1–3** + **S2-TRAJ** · 默认 CP-SAT  
> **叙事**：仓内 SOFA/GBDT；**不**读 decision 风险分；有轨迹包仍**不**宣称 online MIMIC-PPO  
> 方向：[TEAM_DIRECTION.md](TEAM_DIRECTION.md) · 整合：[INTEGRATION_PREP.md](INTEGRATION_PREP.md) · [S2_MULTI_OBJECTIVE.md](S2_MULTI_OBJECTIVE.md)

## 数据

| 项 | 状态 |
|----|------|
| Layer0 labevents | ✅ 158,374,764 |
| feat.sofa_timeseries | ✅ 94,458（真实 SOFA · 0~12 · avg 4.74）|
| dump | ✅ `dumps/icu_scheduling_P0-full_mimic_94458stays_20260802.dump` · 见 [`DUMP_READY.md`](DUMP_READY.md) |
| 交互台 | ✅ **Plotly Ops 台 v4** 项目/运行/验收 · `.\scripts\run_console.ps1` |
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

## CP-SAT 增强（B · 2026-08-01）

- **calib/eval 子集限制**：`run_assignment(split="calib"|"eval")` · 70/30 · seed=42（[`eval_split.py`](`domain/optimizer/eval_split.py`)）
- **业务指标 13 项**：新增 unassigned / high_risk_waiting / avg_assigned_sofa / isolation_utilization / ventilator_utilization
- **可复现**：候选排序加 stay_id tiebreaker；`.gitattributes` 统一 LF
- **可解释报告**：`python -m domain.optimizer.explain [--split ...]` + Streamlit 面板组件化展示

## λ 调参（B · 2026-08-02）

- **quick 16 组 + 完整 256 组合 calib 实验完成** → `reports/lambda_tuning_*.csv|json`（不入库）
- 推荐候选已写回 `optimizer.yaml`：`wait=0.5, overload=0.1, balance=0.1, zone_mismatch=0.1`（+ occupancy 2.0）
- **eval 30% 验证通过**（无过拟合，指标优于 calib）
- 详见 [`LAMBDA_TUNING.md`](LAMBDA_TUNING.md) · 约束边界见 [`PARAM_STORY.md`](PARAM_STORY.md)

## 调参 / 可视化

| 项 | 入口 |
|----|------|
| Streamlit | `streamlit run presentation/streamlit_app.py` |
| MLflow | `mlflow ui --backend-store-uri sqlite:///./mlflow.db` |
| 说明 | [`TUNING_LOCAL.md`](TUNING_LOCAL.md) |
| S2-MOO | ✅ PR#10 三模式 · **阶段 2**：`overload`=高危落普通床 SOFA；`wait`≡priority_served · 见 [`S2_MULTI_OBJECTIVE.md`](S2_MULTI_OBJECTIVE.md) |
| S2-TRAJ | ✅ 协议 1.0 导出验收 · `export_trajectory --steps 4` + schema 单测 · 见 [`TRAJECTORY_PROTOCOL.md`](TRAJECTORY_PROTOCOL.md) |
| PPO smoke | [`PPO_SMOKE.md`](PPO_SMOKE.md) · 代码在 main · **默认 cp_sat** · 离线轨迹≠ online |
| 约束规则 | [`constraint_rules.yaml`](../configs/constraint_rules.yaml) · explain 披露启发式边界 |
| RL 权重 | `optimizer.yaml` → `rl.reward_weights`（与 λ 解耦，含 occupancy） |
| SOTA 对标 | [`SOTA_SURVEY.md`](SOTA_SURVEY.md) · 假设 H1–H3 |
| 数据飞轮 | [`DATA_FLYWHEEL.md`](DATA_FLYWHEEL.md) · `reports/flywheel/`（simulate / evaluate_ppo 自动归档） |

## 说明

- `candidate_cap` 只限制 CP-SAT 候选，**不**裁剪 labs/SOFA/feat
- **dump 可支撑** CP-SAT/仿真；**不可**单独支撑 online PPO 轨迹
- PR #3 已于 2026-07-30 合入 main；`policy.default` 仍为 `cp_sat`
- λ 搜索与推荐候选已写回；PPO 为对照轨（见 [`PPO_SMOKE.md`](PPO_SMOKE.md)）
- GitHub（2026-09-13）：主线 PR #8 已合入；轨迹协议与对照表见 [`TEAM_DIRECTION.md`](TEAM_DIRECTION.md)
- 进度看板：`d:\project\_local-data\mimic\PROGRESS.md`（本地）
