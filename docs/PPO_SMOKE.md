# PPO 合成 Smoke（Draft · 不合 main）

> 更新：2026-07-27 · 选项 **A**：仅合成环境冒烟，**不是** MIMIC online 轨迹交付

## 人读摘要

| 项 | 内容 |
|----|------|
| 分支 | `feat/cp-sat-multi-obj`（PR #3 Draft） |
| 本地 worktree | `d:\project\_wt-scheduling-pr3`（可选） |
| 能证明 | Gymnasium env + MaskablePPO **短步**可跑 |
| **不能**宣称 | 已用全量 MIMIC 训好 online PPO |

## 命令（PowerShell）

```powershell
# 方式 1：已有 worktree
cd d:\project\_wt-scheduling-pr3
$env:PYTHONPATH = (Get-Location)
# 使用 scheduling 仓 venv 或本 worktree 自建
d:\project\icu-scheduling-agent\.venv\Scripts\pip.exe install -q "gymnasium" "sb3-contrib" "stable-baselines3" "ortools"
d:\project\icu-scheduling-agent\.venv\Scripts\python.exe -m pytest tests/test_ppo_training_smoke.py tests/test_rl_env.py -q

# 方式 2：临时 checkout（勿合 main）
cd d:\project\icu-scheduling-agent
git fetch origin feat/cp-sat-multi-obj
git switch --detach origin/feat/cp-sat-multi-obj
# …跑同上测试后：
git switch main
```

## Agent 上下文

```text
main 默认 policy=cp_sat；PPO 保持 Draft
数据底座（labs/SOFA/dump）在 main，供 CP-SAT 与后续真轨迹
真轨迹 / sim 表规范仍归 B + PR 审查
可视化：streamlit + 可选 mlflow ui（见 docs/TUNING_LOCAL.md）
```
