# 方向同步（组员必读）· 2026-09-24

> Owner：`TinjiYDon` · 已合入：PR [#10](https://github.com/TinjiYDon/icu-scheduling-agent/pull/10) → `main`  
> 请 `git pull origin main` 后阅读；有异议在 Issue / 群内回复。

## 人读摘要

| 项 | 内容 |
|----|------|
| 定位 | **独立** 多目标多约束滚动床位调度 + RL 对照轨 |
| 禁止 | 读取 decision `risk_score`；无轨迹协议宣称 online MIMIC-PPO |
| 本周合入 | 组员 **S2-MOO**：Weighted / Lexicographic / ε-Constraint（PR #10 · Mengziyang111） |
| 默认策略 | 仍为 **CP-SAT**；新模式为对照实验开关 |

## 命名对照（避免和旧 ROADMAP「S2」混淆）

| 编号 | 含义 | 状态 |
|------|------|------|
| **S2-MOO**（本次） | 多目标求解模式内核（加权和 / 字典序 / ε-约束） | ✅ PR #10 已合 |
| 旧 ROADMAP **S2** | 轨迹协议 → `artifacts/trajectories/` | ⏳ 下一阶段重点 |
| 旧 ROADMAP **S1** | 约束规则 + 到达强度 | ✅ 骨架已在 main（PR#8） |
| 旧 ROADMAP **S3** | 多目标约束 RL + 三方对照 | ⏳ 在 S2-MOO 之上继续 |

## 已合入改动（请 Review）

- `domain/optimizer/multiobjective.py`  
- `cp_sat.run_assignment(objective_mode=...)`  
- `docs/S2_MULTI_OBJECTIVE.md`（含 calib 三种模式 OPTIMAL 冒烟表）  
- `tests/test_multiobjective.py`  

## 验收命令

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m pytest tests/test_multiobjective.py tests/test_cp_sat_split.py tests/test_lambda_weights.py -q
# 可选：对照表
# .\.venv\Scripts\python.exe -m application.compare_policies --from-report reports/ppo_evaluation.json
```

## 下一阶段（Owner 建议）

| 优先级 | 项 | Owner 建议 |
|--------|----|------------|
| P0 | S2-MOO 阶段 2：指标重定义（真实 wait / overload 床日） | B |
| P0 | 轨迹协议导出验收（旧 ROADMAP S2） | A + B |
| P1 | ε-约束 payoff / Pareto 扫描（文档阶段 3） | B |
| P1 | calib/eval 固定场景包 + 对照写入 STATUS | C |
| P2 | Streamlit 展示三种模式结果 | C |
| 禁 | 读 decision 风险分；无轨迹宣称 online PPO | 全员 |

## Agent 上下文

```text
SSOT: docs/STATUS.md · docs/TEAM_DIRECTION.md · docs/S2_MULTI_OBJECTIVE.md
merged: PR#10 S2-MOO
禁区: dumps/ artifacts/ · 禁止 priority_weight ← decision risk_score
```
