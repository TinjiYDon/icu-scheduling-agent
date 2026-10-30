# PPO 合成 Smoke 与现有检查点验收（默认 CP-SAT）

> 核对：2026-10-30 · PR #3 **已合 main**；现有检查点单轮及 3 episode fair benchmark 已通过，轨迹协议 2.0 真跑 4 步已通过。前轮 29 项无 DB 测试仅支持合成 smoke/接口验证，不作为检查点验收证据。

## 人读摘要

| 项 | 内容 |
|----|------|
| 代码位置 | `main` · `domain/rl/` · `application/train_ppo.py` |
| 默认策略 | `configs/optimizer.yaml` → `policy.default: cp_sat` |
| 合成 smoke 的证据 | `test_ppo_training_smoke.py` 新建合成 `ICUEnv` 与 `MaskablePPO`，训练 16 步后推理；不读取 `artifacts/ppo_icu.zip`。接口与 mask 单测也不等于该检查点验收 |
| 现有检查点 | `artifacts/ppo_icu.zip` 已于 2026-10-30 实际加载并完成 `evaluate_ppo`；历史 200K 步训练及交接记录保留于 [TASK_CHECKLIST_20260731.md](TASK_CHECKLIST_20260731.md) / [PPO_MODEL_HANDOFF.md](PPO_MODEL_HANDOFF.md) |
| 当前 DB | 本机 `icu_scheduling` 已只读核对成功，三个输入表各 94,458 行，详见 [ROADMAP_EXEC.md](ROADMAP_EXEC.md)；未核对 `sim` 表，不推断其为空 |
| 轨迹与训练边界 | S2-TRAJ 协议 2.0 已真跑验收，记录仿真中的分床与周转 ID；不等于逐患者真实临床时间顺序状态。`train_ppo` 通过 `build_icu_env(training=True)` 与环境交互，不消费导出包 |
| **仍未闭环** | 逐患者临床时间顺序状态、独立留出/多种子科学验证；真实床旁事件轨迹和固定数据 offline RL 算法未实现，临床训练证据未交付 |

## 历史记录与本次验收

- 保留 2026-08-02 的 200K 步训练/评估记录与 2026-08-04 的 benchmark 记录。补跑前核对到的旧 `ppo_evaluation.json` 中 PPO/Greedy 用 20 名候选、CP-SAT 用 200 名；旧 `ppo_benchmark.json` 仅 1 episode，缺少当前同资源协议字段，不能直接作为当前 fair 多 episode 验收。
- 保留 2026-09-24 的轨迹协议 schema 单测与 `--steps 4` 导出验收；这是滚动仿真包验收，不是床旁事件日志交付。
- [x] 现有 zip 的 `evaluate_ppo` 真跑冒烟（2026-10-30）：在 MIMIC 94,458 行特征库下加载、推理与公平对照成功；同池 20 stay_ids、20 床，`fair_pool=true`，PPO/Greedy/CP-SAT 均 assigned=5、constraint_violations=0。`reports/ppo_evaluation.json` 与 `reports/flywheel/ppo_eval_latest.json` 已生成并核对。
- [x] 本次 3 episode `evaluate_ppo_benchmark`（2026-10-30）：同池同资源，PPO/Greedy/CP-SAT 均 mean_assigned=5、mean_high_risk_wait=15、mean_constraint_violations=0，`reports/ppo_benchmark.json` 已生成并核对。当前采样评估不自动成为训练患者互斥的独立留出评估。
- [x] 轨迹协议 2.0 `export_trajectory --steps 4`（2026-10-30）：真实导出 4 transitions；`state` 为转移前、`next_state` 为转移后，前后连续性和每步人数守恒已断言验证，全部 `constraint_check_status="checked"` 且 `constraint_violation=false`。未知检查仍应为 null，不能写成通过；奖励仍为未加权仿真代理，非 PPO 训练奖励或临床证据。

最终完整 pytest 为 217 passed / 6 skipped，另只读 DB 集成 3 passed；未运行会写数据的 ETL。零周转退队列（默认保留在院患者）及 CP/RL 的 ISO 错配豁免已修复，真实 CP 零周转与两类 zone 回归通过；按最终代码重新生成了 PPO、H5、H6 与轨迹报告。40 人 bake-off/H5、多目标与 H6 的分版本结果见 [ROADMAP_EXEC.md](ROADMAP_EXEC.md)。

## 合成 smoke 命令（子集）

在仓库根目录、使用已有依赖环境执行：

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m pytest tests/test_ppo_training_smoke.py tests/test_rl_env.py -q
```

## 现有检查点 / 仿真轨迹复验命令

以下为复现入口；本次 `evaluate_ppo`、3 episode benchmark 及轨迹 2.0 导出已按上述范围验收，不据此推断单独 CLI 或研究结论全部通过。`evaluate_ppo*` 会写本地报告，轨迹包写入 `artifacts/trajectories/`，均不入 Git；不以重新训练覆盖现有检查点来替代复验。

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m application.run_ppo
.\.venv\Scripts\python.exe -m application.evaluate_ppo
.\.venv\Scripts\python.exe -m application.evaluate_ppo_benchmark --episodes 3
.\.venv\Scripts\python.exe -m application.export_trajectory --steps 4
```

## Agent 上下文

```text
PR #3 merged；默认仍 cp_sat
PR #16 merged；HEAD=34fe955
DB 已只读核对；不因沙箱 TCP 拒绝推断 PostgreSQL 未启动
29 项无 DB 测试 ≠ 现有 zip 复验；本次现有 zip 的 evaluate_ppo 冒烟已过
同池20人+20床，PPO/Greedy/CP-SAT各assigned=5，constraint_violations=0
3 episode fair benchmark已过：三策略mean_assigned=5、mean_high_risk_wait=15、违约0
轨迹2.0真实4步已过：连续性/人数守恒/checked且无违规均已断言
最终H6共享初态并保留在院患者：8步18vs18打平，均违约0；pytest217passed6skipped
两项边界已修：默认retain_occupied=True并强制留院；CP/RL错配豁免统一，已补回归
研究缺口：逐患者临床时序状态、独立留出/多种子；offline RL算法未实现
普通 PPO 是仿真交互训练；离线评估 ≠ offline RL 训练
可视化：docs/TUNING_LOCAL.md
```
