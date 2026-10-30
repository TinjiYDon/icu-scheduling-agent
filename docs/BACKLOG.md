# 任务 Backlog

> 当前核对：2026-10-30。下列已勾选项保留工程交付与历史验收记录，不代表 H1–H7 已充分验证。PR #16 已合 main（`HEAD=34fe955`）；本机 DB 只读核对成功，当前不是环境阻塞。当前证据见 [ROADMAP_EXEC.md](ROADMAP_EXEC.md)，PPO 验收边界见 [PPO_SMOKE.md](PPO_SMOKE.md)。

---

## S0 ✓

- [x] ETL + dump + 冒烟（A）

---

## S1 · SOFA

- [x] **#S1-1** B：`domain/scoring/sofa.py` 写入 `feat.sofa_*`（STATUS 已有真实 SOFA ✅）
- [x] **#S1-2** A：ETL/labs + full dump（Owner dump 20260727 ✅）

---

## S3 · Streamlit

- [x] **#S3-1** C：`presentation/streamlit_app.py` 展示状态 → 分配方案 ✅
  - L4：`application/plan.py` · 只调 L4

---

## S2 · CP-SAT 仿真（B + C）

- [x] **#S2-1** B：`domain/optimizer/cp_sat.py` 20 床 demo ✅
- [x] **#S2-2** B：`application/simulate.py` 端到端 + STATUS 数值（**Wave2** ✅ 2026-07-31）
- [x] **#S2-3** C：`application/plan.py` + `data_access/assignments_repo.py` ✅
- [x] **#S2-3b** C：calib/eval 骨架 + metrics 键（**Wave1** ✅ 2026-07-25）
- [x] **#S3-1b** Streamlit 目标分解 metrics、`not_found` 状态 ✅

---

## S4 · 进阶

- [x] **#S4-1a** B：PPO/lambda 代码入 main（PR #3 ✅ 2026-07-30 · 默认仍 cp_sat）
- [x] **#S4-1b-partial** C：滚动仿真轨迹导出协议 `docs/TRAJECTORY_PROTOCOL.md` + `application.export_trajectory`（**非** MIMIC 床旁事件日志）
- [x] **现有 PPO 检查点真跑冒烟**（2026-10-30）：实际加载 `artifacts/ppo_icu.zip`，在 MIMIC 94,458 行特征库下完成 `evaluate_ppo`；同池 20 人 + 20 床，PPO/Greedy/CP-SAT 各 assigned=5、constraint_violations=0，报告与 flywheel 已生成。证据来自本次实测，不是前轮 29 项无 DB 测试。
- [x] **PPO 3 episode benchmark**（2026-10-30）：同池同资源，三策略 mean_assigned=5、mean_high_risk_wait=15、mean_constraint_violations=0，报告已生成。
- [x] **滚动仿真轨迹 2.0 复验**（2026-10-30）：`export_trajectory --steps 4` 真跑生成 4 transitions；真实 JSON 的 state/next_state 连续性、每步人数守恒及 `constraint_check_status=checked`、`constraint_violation=false` 均已断言核验。保留 2026-09-24 协议 1.0 历史验收，非床旁事件轨迹。
- [x] **40 人 bake-off / H5**（2026-10-30）：修复候选 40 被默认 20 截断后，两个本地报告均已生成。
- [x] **多目标复验**（2026-10-30）：eval 六场景 18 个 WS/Lex/ε 求解全部 OPTIMAL；阶段 3 为 27 grid / 17 feasible / 3 nondominated / HV=0.052130。旧结果按历史版本保留，详见 [ROADMAP_EXEC.md](ROADMAP_EXEC.md)。
- [x] **H6 最终验收**（2026-10-30）：共享初始分配并默认保留在院患者，8 步 rolling / greedy 期末均为 18，均无违约、求解失败或被动退队列。本设定打平。
- [ ] **#S4-1b 研究支线** B：逐患者临床时间顺序状态、独立留出与多种子科学验证仍未闭环；真实床旁事件轨迹与固定数据 offline RL 算法（如 CQL/IQL）未实现。普通 PPO 仿真交互训练不关闭此项。
- [x] **独立代码复核边界修复**：滚动默认 `retain_occupied=True`，CP 强制在院患者继续分床并检查返回结果不丢人；仅显式 `False` 保留旧退队列行为。CP/RL 已统一真正隔离需求 + ISO 床的错配豁免，其余非偏好分配计错配；真实 CP 零周转及两类 zone 回归均通过。
- [x] **最终重跑**：PPO、H5、H6、轨迹、六场景与 Pareto 报告已按最终代码生成，结果见 [LOCAL_VALIDATION_20261030.md](LOCAL_VALIDATION_20261030.md)。
- [x] **#S4-2** C：MCP `optimize_beds`（骨架 ✅ 2026-07-22）

最终完整 pytest：217 passed / 6 skipped；另只读 DB 集成 3 passed，未运行会写数据的 ETL。默认 CP-SAT；`hybrid` 是有意预留，非必做项。测试与仿真验收不代表临床或研究已充分验证。

---

## 基础设施

- [x] **#INF-1** A：pytest CI（`.github/workflows/ci.yml` ✅）
- [x] **#INF-2** C：PR checklist（`.github/pull_request_template.md` ✅）
