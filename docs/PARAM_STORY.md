# 参数与数据故事（人机可读）

> Owner：C 维护 · B SOFA/CP-SAT · A ETL/dump  
> 更新：2026-07-22 · RL 路线：**B 数据底座 + A审 PR#3**（PPO 不进 main）

## 调度目标（P0）

| 概念 | 含义 | 代码/表 |
|------|------|---------|
| `priority_weight` | 越高越优先占床 | SOFA 推导或 ETL 占位 → `feat.patient_priority` |
| SOFA（简化） | 肌酐/胆红素/血小板 → renal/liver/coag | `domain/scoring/sofa.py`（需 Layer0 labs） |
| CP-SAT | 0-1 分配 stay↔bed | `domain/optimizer/cp_sat.py` → `sched.assignments` |
| lambda.* | 多目标权重 | `configs/optimizer.yaml`；**main 未全用**，见 Draft PR #3 |

## 资源（配置）

| 参数 | 默认 | 说明 |
|------|------|------|
| `n_beds` | 20 | 当前求解使用 |
| `n_isolation_beds` / `n_ventilators` | 配置有 | P0 求解未完整约束 |

## dump / RL

schemas_only dump **不能**支撑 online PPO。需要：`sim` 轨迹或完整 feat + Layer0。PR #3 提供合成环境 smoke，真训练另议。

## 验收

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m pytest tests/test_plan.py -q
```
