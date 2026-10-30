# 任务清单 · 2026-07-31（持续更新）

> 历史数据里程碑（2026-07-27）：真实 MIMIC 已导入，彼时导入阻塞解除 ✅
> 当前核对：2026-10-30。本文件保留历史分工及验收记录，不表示研究已充分验证。PPO 单轮/3 episode、轨迹 2.0、40 人 H5/bake-off、多目标及共享初态版 H6 本次验收已回填，详见 [ROADMAP_EXEC.md](ROADMAP_EXEC.md) / [PPO_SMOKE.md](PPO_SMOKE.md)。PR #16 已合 main（`HEAD=34fe955`）。

---

## 🎉 历史重大进展（队友/Owner 完成）

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
| 5 | λ 网格搜索（quick + 完整 256）| quick 16 组 + 完整 256 组 calib 实验 + eval 验证；当时推荐值待队友确认，当前写回状态见下文 | 08-01/02 |
| 6 | 可解释输出 | `explain.py` CLI + 队友 v4 面板 plan["explain"] 接入 | 08-01 |
| 7 | PPO 训练 | 历史记录：完整 200K 步，`artifacts/ppo_icu.zip`，当时评估 PPO≈Greedy；不替代本次检查点复验 | 08-02 |
| 8 | PPO 深入对比 | `application/evaluate_ppo_benchmark.py` 多 episode 入口已实现；补跑前旧报告仅 1 episode，本次协议复验见下文 | 08-04 |
| 9 | 面板前端可解释 | KPI help / 三图各占一行+解释 / 坐标轴 / 表格列说明 | 08-05 |
| 10 | 参数真实生效 | `n_beds` 可调、`candidate_cap`/`max_time` 生效、改参数自动重跑 | 08-05/06 |
| 11 | 滚动每步 CP-SAT | 历史交付：每步重优化 + f5 挪床惩罚 + 呼吸机 SOFA 驱动；本次共享初态版 H6 与旧数字分版本记录，见执行路线图 | 08-06 |

---

## 📌 待办与本次验收

| # | 任务 | 说明 | 阻塞/前置 |
|:-:|------|------|:--:|
| 12 | λ 推荐值写回 / 业务确认 | ✅ 当前 `optimizer.yaml` 已采用完整网格推荐值，历史 eval 记录见 `LAMBDA_TUNING.md`；队友六场景业务确认未见单独记录，不能仅据配置写回认定已确认 | 业务确认待核证 |
| 13 | 现有 PPO 检查点真跑冒烟 | ✅ 2026-10-30 `evaluate_ppo`；同池 20 人 + 20 床，三策略各 assigned=5、constraint_violations=0；当前报告与 flywheel 已生成 | 已完成 |
| 14 | 滚动仿真轨迹复验 | ✅ 协议 2.0 真跑 4 transitions，连续性/人数守恒/checked 且无违规已断言；旧 1.0 验收保留 | 已完成 |
| 15 | PPO 3 episode benchmark | ✅ 同池同资源；三策略 mean_assigned=5、mean_high_risk_wait=15、mean_constraint_violations=0 | 已完成 |
| 16 | 40 人 H5 / bake-off | ✅ 两报告已生成，候选 40 被默认 20 截断已修复 | 已完成 |
| 17 | H6 共享初始分配版 | 2026-10-30 最终 8 步 rolling/greedy 期末均 18，默认保留在院患者、均无违约，本设定打平 | 已完成 |
| 18 | 多目标重跑 | ✅ eval 六场景 18 个 OPTIMAL；阶段 3 新结果 27/17/3/HV=0.052130 | 已完成 |
| 19 | 核心科学验证 | 临床时间顺序状态、独立留出/多种子仍未闭环 | 未闭环 |
| 20 | 独立代码复核边界修复 | 默认强制保留在院患者并检查返回，legacy 退队列须显式关闭保留；CP/RL 的 ISO 错配豁免语义统一，回归和重跑均通过 | 已完成 |

## 📌 队友待完成

| # | 任务 | 主责 / 当前证据 |
|:-:|------|------|
| 11 | pytest CI 流水线 | A · ✅ `.github/workflows/ci.yml` 已存在；不据此宣称当前 CI 全通过 |
| 12 | PR checklist | C · ✅ `.github/pull_request_template.md` 已存在 |
| 13 | PPO 验收（你的成果） | C 审核 · 现有 zip 单轮及 3 episode fair benchmark ✅ 2026-10-30；29 项无 DB 测试仅支持合成 smoke |

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

**阶段验收已回填、两项代码边界已修并补回归 → 等待修复后的最终重跑数字 → 补逐患者临床时间顺序状态与独立留出/多种子科学验证；默认仍保持 CP-SAT。**

最终完整 pytest 为 217 passed / 6 skipped，另只读 DB 集成 3 passed；未运行会写数据的 ETL。真实床旁事件轨迹、固定数据 offline RL 算法（如 CQL/IQL）仍未实现，历史 200K 步 PPO 是仿真内交互训练。`hybrid` 为有意预留，非必做项。
