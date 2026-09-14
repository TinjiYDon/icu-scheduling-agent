# 参数与数据故事（人机可读）

> Owner：C 维护 · B SOFA/CP-SAT/RL · A ETL/dump  
> 更新：2026-09-13 · 默认 `cp_sat`；ISO/vent **求解已实现**，需求标记仍有简化边界

## 调度目标（P0）

| 概念 | 含义 | 代码/表 |
|------|------|---------|
| `priority_weight` | 越高越优先占床 | 仓内 GBDT 或 SOFA 规则 → `feat.patient_priority` |
| SOFA（简化） | 肌酐/胆红素/血小板 → renal/liver/coag | `domain/scoring/sofa.py`（需 Layer0 labs） |
| CP-SAT | 0-1 分配 stay↔bed | `domain/optimizer/cp_sat.py` → `sched.assignments` |
| lambda.* | 多目标权重 | `configs/optimizer.yaml`（wait/overload/balance/zone；occupancy） |

## 资源与硬约束（诚实边界）

| 参数 | 默认 | 说明 |
|------|------|------|
| `n_beds` | 20 | 当前求解使用 |
| `n_isolation_beds` | 4 | CP-SAT：**隔离患者只能分到前 N 张隔离床** |
| `n_ventilators` | 8 | CP-SAT：**全局 portable 计数**上限（非逐床真实设备台账） |

**需求如何标记（当前简化，非临床金标准）：**

- 隔离需求：careunit 关键词启发式（可配置，见 `configs/constraint_rules.yaml`）
- 呼吸机需求：可配置规则或 stay_id 稳定哈希比例（演示用）；以配置为准并在 explain 中披露

## 滚动参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `rolling.step_hours` | 2 | 滚动步长 |
| `rolling.admission_rate` / `discharge_rate` | 0.05 | 可由 `train_priority --intensity-only` 用 MIMIC 校准后写回 |

## dump / RL

- dump **可支撑** CP-SAT / 滚动仿真。
- **不能**仅凭 schemas_only 宣称 online MIMIC-PPO。
- 轨迹协议：见 `docs/TRAJECTORY_PROTOCOL.md`；导出目录 `artifacts/trajectories/`（不入 Git）。
- `policy.default` 保持 `cp_sat`；PPO 为对照轨。

## 验收

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m pytest tests/test_plan.py tests/test_rl_env.py -q
.\.venv\Scripts\python.exe -m application.simulate
```
