# 执行路线图 ROADMAP_EXEC

> 核对：2026-10-30 · **滚动时域调度**为主叙事；保留历史验收，当前状态以环境与实测证据区分。

## 人读摘要

| Wave | 含义 | 状态 |
|------|------|------|
| **1** | calib/eval + simulate metrics | ✅ |
| **2** | SOFA→feat + STATUS 数字 | ✅ |
| **实时** | 滚动每步状态→CP-SAT | 共享初态版 H6 阶段验收保留；两项复核边界已修并补回归，待修复后最终重跑数字 |
| **PPO** | 代码在 main | 默认未启用；现有检查点单轮与 3 episode fair benchmark ✅ 2026-10-30 |
| **S2-TRAJ** | 滚动仿真导出协议 | 2.0 真跑 4 transitions 已验收，保留 2026-09-24 的 1.0 历史；非床旁事件日志 |

上述 ✅ 仅表示注明日期与范围的工程验收，不能推导研究假设已充分验证。

## 当前环境与证据（2026-10-30）

| 核对项 | 证据 / 结论 |
|--------|-------------|
| 主线 | `HEAD=34fe955`，merge commit 已包含 PR #16，该 PR 不再列为待合并 |
| DB 可用性 | 沙箱外只读查询本机 `icu_scheduling` 成功，不存在恢复 DB / 环境阻塞 |
| 输入表 | `staging.icustays=94458`、`feat.sofa_timeseries=94458`、`feat.patient_priority=94458`；行数核对不等于模型或临床有效性验证 |
| `sim` 表 | 本次未提供核对结果，不声称为空；现有 PPO 从 MIMIC 特征构建仿真环境，不以 `sim` 表作为已知前置 |
| 合成 smoke | 已包含在本次完整单测中；训练测试新建合成模型，不加载现有 zip，检查点另行真跑 |
| 现有 PPO 检查点 | ✅ 2026-10-30 已实际加载 `artifacts/ppo_icu.zip` 并完成 `evaluate_ppo`；MIMIC 94,458 行特征库，同池 20 人 + 20 床，三策略各 assigned=5、constraint_violations=0；`reports/ppo_evaluation.json` 与 flywheel 已生成并核对 |
| PPO 多 episode | ✅ 3 episode 同池同资源；三策略 mean_assigned=5、mean_high_risk_wait=15、mean_constraint_violations=0，`reports/ppo_benchmark.json` 已生成并核对 |
| 滚动仿真轨迹 | ✅ 协议 2.0 `export_trajectory --steps 4` 真跑 4 transitions；真实 JSON 的 state/next_state 连续性、每步人数守恒均已断言，全部 `constraint_check_status="checked"` 且 `constraint_violation=false`，不是未检查，也不是床旁轨迹 |
| 40 人 bake-off / H5 | ✅ 两个本地报告已生成并核对，候选 40 被默认 20 截断已修复；`scikit-learn` 已补入依赖 |
| eval 六场景 | ✅ WS/Lex/ε 共 18 次求解全部 OPTIMAL，`reports/moo/scenarios_latest.json` 已生成并核对 |
| H6 / 共享初始分配 | 最终 8 步 rolling / greedy 均 18 床，均 SOFA=10.0667、权重=2.0056、无违约、无求解失败、无退队列；默认保留在院患者，第二策略复用首策略 history[0] 并重新校验，本设定打平 |
| 最终完整 pytest | 217 passed / 6 skipped；含真实 CP 零周转与两类 zone 回归，不能用工程测试替代研究验证 |
| DB 集成测试 | 只读 3 passed；未运行会写数据的 ETL |

## 新旧结果分版本保存

| 实验 | 历史记录 | 2026-10-30 最终修复工作区结果 |
|------|----------|------------------------------------------------|
| H6 8 步 | 2026-10-09：rolling 最终 18、greedy 20；仅为旧引擎历史 | 共享初始分配，默认保留在院患者：rolling / greedy 均 18 床、均违约 0，本设定打平 |
| 阶段 3 payoff / ε-grid / HV | 2026-09-24：81 grid / 54 feasible / 4 nondominated / HV=0.038794 | 27 grid / 17 feasible / 3 nondominated / HV=0.052130；不能跨版本直接宣称改进 |

本次完整结果已同步 `STATUS.md` 与 `LOCAL_VALIDATION_20261030.md`；本次 payoff 的 balance 轴退化，去重后为 27 点，并非固定 81 点，不跨版本直接比较 HV。

沙箱 TCP 拒绝只说明该次连接受限，不能据此判断 PostgreSQL 未启动。`docs/STATUS.md` 保留历史数字，不能替代上表本次核验。

## 修复记录与研究待办

- 已完成：PPO 检查点单轮/3 episode、协议 2.0 真实导出、40 人 H5/bake-off、eval 六场景、阶段 3 以及共享初态版 H6，均按本次实测证据验收。标准与入口见 [PPO_SMOKE.md](PPO_SMOKE.md)，不以 29 项合成测试替代检查点实测。
- 留院边界已修并验证：滚动默认 `retain_occupied=True`，CP 对现住院患者强制 `sum(x)=1`，并校验求解返回不能丢人；legacy 退队列行为须显式 `retain_occupied=False`。真实 CP 零周转回归通过。修复前曾以 1 张普通床、同权重 SOFA=10/12、λ(occupancy/wait/overload)=1/0.1/1.2、balance=zone_mismatch=0、move=0.5、零入出院率复现占用 1→0，当前不再发生。
- 科室错配边界已修并验证：CP/RL 统一为仅真正 `needs_iso` 且使用 ISO 床时豁免错配；其余非偏好分配（含偏好科室不存在）计错配。新增两类 zone 回归通过。修复前 CCU 非隔离患者使用 ISO+CCU 床时出现 CP=0、RL=-0.5 的惩罚差异，当前口径一致。
- 工程待办的最终重跑与结果回写均完成；研究问题保留为独立待办。
- 核心研究未闭环：逐患者临床时间顺序状态、独立留出与多种子科学验证。真实床旁事件轨迹、固定数据 offline RL 算法（如 CQL/IQL）与临床训练证据尚未实现/交付；`train_ppo` 与仿真环境交互，不消费导出包，随机抽样 benchmark 不自动构成训练患者互斥的留出评估。
- H1–H7 的既有代码、文档与小规模结果不等于充分研究验证；继续按假设验收对照、稳健性与局限。`hybrid` 是有意预留的非必做项。

## Agent 上下文

```text
主路径：python -m application.simulate（rolling）
配置：policy.default=cp_sat
单测入口：pytest tests/test_simulate_metrics.py tests/test_plan.py -q（无 DB 契约，不代表检查点或 DB 集成验收）
当前：PPO单轮/3episode、轨迹2.0真跑4步、40人H5/bakeoff、六场景18个OPTIMAL已过
H6最终：共享初态、保留在院患者，8步18vs18打平，均违约0
pytest最终217passed6skipped；另只读DB3passed，未运行ETL写数据测试
两项边界已修并补回归：默认强制留院及返回校验；CP/RL错配语义统一，待最终重跑验证
阶段3新27/17/3/HV0.052130与历史版本另存；未运行ETL写数据测试
研究未闭环：临床时序状态/独立留出/多种子；offline RL算法未实现
禁止：宣称 online PPO 已用 MIMIC 训好
```
