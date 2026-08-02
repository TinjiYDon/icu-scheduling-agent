# PPO 合成 Smoke（代码已在 main · 默认未启用）

> 更新：2026-08-02 · PR #3 **已合 main**（2026-07-30）；**不是** MIMIC online 轨迹交付

## 人读摘要

| 项 | 内容 |
|----|------|
| 代码位置 | `main` · `domain/rl/` · `application/train_ppo.py` |
| 默认策略 | `configs/optimizer.yaml` → `policy.default: **cp_sat**` |
| 能证明 | Gymnasium env + MaskablePPO **短步**可跑 |
| **不能**宣称 | 已用全量 MIMIC 训好 online PPO；`sim` 轨迹表仍空 |

## 命令

```powershell
cd d:\project\icu-scheduling-agent
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\pip.exe install -q "gymnasium" "sb3-contrib" "stable-baselines3"
.\.venv\Scripts\python.exe -m pytest tests/test_ppo_training_smoke.py tests/test_rl_env.py -q
```

## Agent 上下文

```text
PR #3 merged；默认仍 cp_sat
无 MIMIC 轨迹包；合成 smoke ≠ 真训
可视化：docs/TUNING_LOCAL.md
```
