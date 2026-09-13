# 轨迹协议 · ICU Scheduling RL（S2）

> 更新：2026-09-13  
> **未齐本协议前，禁止在 STATUS 宣称 online MIMIC-PPO 训练成功。**

## 目的

为 MaskablePPO / 多目标约束 RL 提供**可复现**的离线 transition 包，与 CP-SAT 滚动仿真对齐语义。

## 导出

```powershell
cd d:\project\icu-scheduling-agent
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m application.export_trajectory --steps 12
```

输出（**不入 Git**）：`artifacts/trajectories/rolling_traj_*.json` 与 `rolling_traj_latest.json`。

## Schema（protocol_version = 1.0）

| 字段 | 含义 |
|------|------|
| `state.occupied` / `free_beds` | 床态摘要 |
| `state.avg_sofa` / `avg_weight` | 队列/占用病情代理 |
| `action.admitted` / `discharged` | 本步周转 |
| `action.policy` | 产生动作的策略标签 |
| `reward_components` | 与 λ 同构的分量（可扩展 occupancy/wait/…） |
| `constraint_violation` | 硬约束违反标记 |

## 与 CP-SAT / RL 对齐

- 生产默认仍为 `policy.default=cp_sat`。
- RL 奖励权重优先读 `optimizer.yaml` → `rl.reward_weights`，缺省回退 `lambda.*`。
- 本包来自 **rolling 仿真导出**，不是床旁 MIMIC 事件日志；可用于 offline 对照与 smoke，不能单独支撑「真实 online 临床 RL」话术。

## 验收

```powershell
.\.venv\Scripts\python.exe -m application.export_trajectory --steps 4
.\.venv\Scripts\python.exe -m pytest tests/test_trajectory_export.py -q
```
