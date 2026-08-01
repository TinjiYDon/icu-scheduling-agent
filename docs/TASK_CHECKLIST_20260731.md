# 任务清单 · 2026-07-31

> 数据里程碑（2026-07-27）：真实 MIMIC 已导入！阻塞解除 ✅

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

## 📌 需要你（B）完成的任务

| # | 任务 | 说明 | 阻塞 |
|:-:|------|------|:--:|
| 1 | ~~恢复新 dump~~ | ✅ 2026-07-31 已恢复，真实 SOFA 94,458 行入本地库 | — |
| 2 | ~~S2-2 Wave2~~ | ✅ 2026-07-31 真实 SOFA 跑通 simulate，数值已写入 STATUS | — |
| 3 | **calib/eval 子集限制** | 按 70/30 划分，求解只用 calib 集 | ② |
| 4 | ~~CP-SAT 业务指标完善~~ | ✅ 2026-08-01 新增 5 指标（unassigned / high_risk_waiting / avg_assigned_sofa / 隔离与呼吸机利用率）+ 候选 tiebreaker 可复现 | — |
| 5 | **S4-1 PPO** | 保持 Draft PR #3，训 PPO 对比 CP-SAT（不进 main） | ②+ |

---

## 📌 队友待完成

| # | 任务 | 主责 |
|:-:|------|:--:|
| 6 | pytest CI 流水线 | A |
| 7 | PR checklist | C |
| 8 | PPO 验收（你的成果） | C 审核 |

---

## ✅ 你已完成（已合并 main）

- CP-SAT 四目标模型（等待/超负荷/均衡/科室匹配）
- 隔离床 + 呼吸机 + 床位分区约束
- 可解释输出 `explain.py`
- 滚动时域仿真 `rolling/engine.py`
- 合成 SOFA（已被真实数据取代）

---

## 一句话下一步

**先恢复新 dump → 用真实 SOFA 跑一遍 simulate → 填 STATUS 数值 → 再做 PPO。**
