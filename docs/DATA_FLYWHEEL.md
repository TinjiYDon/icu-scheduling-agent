# 数据飞轮 · icu-scheduling-agent

> 更新：2026-09-13 · Wave **S-FLY**  
> **独立闭环**：仿真/评估指标 → λ 或约束复核 / RL 迭代 → 再测。  
> **禁止**：读取 decision `risk_score`；**禁止**无轨迹协议宣称 online MIMIC-PPO。

## 闭环图

```text
simulate / evaluate_ppo / export_trajectory
    → reports/flywheel/*.json（不入 Git）
    → 指标变差？→ λ 重扫 / constraint_rules 复核 / 仅在轨迹包上训 RL
    → 再跑 simulate + evaluate_ppo
```

## 归档约定

| 触发 | 归档位置 | 内容 |
|------|----------|------|
| `python -m application.simulate` | `reports/flywheel/simulate_<ts>.json` + `simulate_latest.json` | 滚动 KPI |
| `python -m application.evaluate_ppo` | `reports/flywheel/ppo_eval_<ts>.json` + `ppo_eval_latest.json` | 三方对照摘要 |
| 轨迹导出 | `artifacts/trajectories/` | 见 TRAJECTORY_PROTOCOL |

`reports/` 已在 `.gitignore`。

## 回流规则

1. 利用率骤降或高危等待上升 → 复核 `lambda.*`（`scripts/tune_lambda.py`）  
2. ISO/vent 利用率异常 → 复核 `configs/constraint_rules.yaml`  
3. RL 仅在有轨迹协议包后迭代；对照始终含 CP-SAT  
4. **不**引入 decision 风险分「自动改善」优先级

## 命令

```powershell
cd d:\project\icu-scheduling-agent
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m application.simulate
.\.venv\Scripts\python.exe -m application.evaluate_ppo
```

## 相关

- [SOTA_SURVEY.md](SOTA_SURVEY.md) · [TRAJECTORY_PROTOCOL.md](TRAJECTORY_PROTOCOL.md) · [LAMBDA_TUNING.md](LAMBDA_TUNING.md)
