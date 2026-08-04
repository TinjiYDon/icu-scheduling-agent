# 任务清单 · 2026-07-31（持续更新）

> 数据里程碑（2026-07-27）：真实 MIMIC 已导入！阻塞解除 ✅
> 更新：2026-08-01 · 任务③④⑤ 完成 · λ quick 实验产出推荐值（待队友确认）

---

## 🎉 最新重大进展（队友/Owner 完成）

| 项 | 状态 | 说明 |
|----|------|------|
| **Layer0 labevents 导入** | ✅ | 158,374,764 行原始化验数据 |
| **真实 SOFA 评分** | ✅ | `feat.sofa_timeseries` 94,458 行 |
| **完整 dump** | ✅ | `icu_scheduling_P0-full_mimic_94458stays_20260727.dump`（schemas_only=false） |
| MCP `optimize_beds` 骨架 | ✅ | `presentation/mcp_server.py` |
| Streamlit + MLflow | ✅ | 本地可视化 + 实验追踪 |
| calib/eval 划分骨架 | ✅ | Wave1 · `domain/optimizer/eval_split.py` |
| Bugbot 追踪 | ✅ | `docs/BUGBOT.md` |

---

## 📌 你（B）已完成的任务

| # | 任务 | 说明 | 完成 |
|:-:|------|------|:--:|
| 1 | 恢复新 dump | 真实 SOFA 94,458 行入本地库 | 07-31 |
| 2 | S2-2 Wave2 | 真实 SOFA 跑通 simulate，数值入 STATUS | 07-31 |
| 3 | calib/eval 子集限制 | `run_assignment(split=...)` 70/30、seed=42 | 08-01 |
| 4 | S2-1 业务指标完善 | +5 指标 + 候选 tiebreaker 可复现 | 08-01 |
| 5 | λ 网格搜索（quick + 完整 256）| quick 16 组 + 完整 256 组 calib 实验 + eval 验证，推荐值待队友确认 | 08-01/02 |
| 6 | 可解释输出 | `explain.py` CLI + 队友 v4 面板 plan["explain"] 接入 | 08-01 |
| 7 | PPO 训练 | 完整 200K 步，`artifacts/ppo_icu.zip`，评估 PPO≈Greedy | 08-02 |
| 8 | PPO 深入对比 | `application/evaluate_ppo_benchmark.py` 同候选规模多 episode 评估 | 08-04 |

---

## 📌 待完成任务

| # | 任务 | 说明 | 阻塞/前置 |
|:-:|------|------|:--:|
| 12 | λ 推荐值确认 | 队友 C 确认 6 场景后再写回 `optimizer.yaml` | 队友 |

## 📌 队友待完成

| # | 任务 | 主责 |
|:-:|------|:--:|
| 11 | pytest CI 流水线 | A |
| 12 | PR checklist | C |
| 13 | PPO 验收（你的成果） | C 审核 |

---

## ✅ 你已完成（分支已推送 origin/feat/cp-sat-multi-obj）

- CP-SAT 四目标模型（等待/超负荷/均衡/科室匹配）
- 隔离床 + 呼吸机 + 床位分区约束
- 可解释输出 `explain.py`（终端 CLI + Streamlit 面板组件化）
- 滚动时域仿真 `rolling/engine.py`
- calib/eval split 限制求解（70/30, seed=42）
- 业务指标 13 项（含 unassigned/high_risk_waiting/avg_assigned_sofa/资源利用率）
- λ 网格搜索（quick 16 组 + 完整 256 组 → `reports/lambda_tuning_*.csv|json`）
- PPO 训练（200K 步，`artifacts/ppo_icu.zip` + `reports/ppo_evaluation.json`）
- 候选排序 tiebreaker + .gitattributes 统一 LF（可复现）

---

## 一句话下一步

**跑完整 256 组合 λ 搜索 → 队友确认推荐值写回 optimizer.yaml → eval 验证 → PPO。**
