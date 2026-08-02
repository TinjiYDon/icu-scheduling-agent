# 参数与数据故事（人机可读）

> Owner：C 维护 · B SOFA/CP-SAT · A ETL/dump  
> 更新：2026-08-02 · RL：代码可在 main（PR#3）；**默认 cp_sat**；真轨迹未交付

## 调度目标（P0）

| 概念 | 含义 | 代码/表 |
|------|------|---------|
| `priority_weight` | 越高越优先占床 | SOFA 推导或 ETL 占位 → `feat.patient_priority` |
| SOFA（简化） | 肌酐/胆红素/血小板 → renal/liver/coag | `domain/scoring/sofa.py`（需 Layer0 labs） |
| CP-SAT | 0-1 分配 stay↔bed | `domain/optimizer/cp_sat.py` → `sched.assignments` |
| lambda.* | 多目标权重 | `configs/optimizer.yaml`（PR #3 已合） |

## 资源（配置）

| 参数 | 默认 | 说明 |
|------|------|------|
| `n_beds` | 20 | 当前求解使用 |
| `n_isolation_beds` / `n_ventilators` | 配置有 | P0 求解未完整约束 |

## dump / RL

schemas_only dump **不能**支撑 online PPO。需要：`sim` 轨迹或完整 feat + Layer0。PR #3 已合 main 提供合成环境 smoke；**MIMIC 轨迹包仍未处理**。

## 验收

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m pytest tests/test_plan.py -q
```
