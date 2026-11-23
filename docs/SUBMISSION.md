# 双创提交版说明（scheduling）

## 版本

- 分支：`release/shuangchuang-2026-11`
- 基线：`origin/main`（`fa9e4b8`，含可复现 Pareto 案例研究与滚动报告）
- 增量：`feat(S1): isolation-mode switch`（`7c6535f`）
- 预计标签：`v2026.11-submit`

## 本次包含

- CP-SAT 单步分床模型：`domain/optimizer/cp_sat.py`
- 多目标 / ε 网格 / HV：`domain/optimizer/moo_phase3.py`
- H10 决策层：`domain/optimizer/pareto_decision.py`
- 滚动与 HV–churn：`domain/rolling/engine.py`、`application/run_hv_churn.py`
- DAC / FD / B_pool：`domain/optimizer/data_contract.py`、`fd_stress.py`、`pool_effect.py`
- 前沿质量指标：`domain/optimizer/front_quality.py`
- 正常负载敏感性开关：`--isolation-mode none`
- 可复现案例研究：`scripts/case_study/`
- 离线依赖快照：`requirements.lock.txt`

## 验证结果（本机，2026-11-23）

```text
官方核心测试：45 passed（plan/smoke/MCP/simulate/isolation/front_quality/case_study）
tests（排除可选 PPO 文件）：230 passed
  1 failed：tests/test_etl.py::test_etl_smoke（数据库账号无 TRUNCATE 权限，环境问题）
可选 PPO 文件：ModuleNotFoundError: sb3_contrib（未安装可选依赖）
preflight：16/16 passed（使用项目 .venv）
```

## 实验边界

1. 主实验报告为 2026-11-13 版本；报告之后新增的前沿质量、隔离模式开关、案例研究**不改变默认策略与默认结果**。
2. `--isolation-mode none` 只用于 S1 正常负载敏感性实验，主报告数字仍为默认 `config` 隔离口径。
3. 报告中的五法 bake-off 同值、H6 贪心占用更高等负结果照原样保留，不作“方法全面更优”的宣称。

## 复现

```powershell
$env:PYTHONPATH=(Get-Location)
.\.venv\Scripts\python.exe -m pytest tests/test_plan.py tests/test_smoke.py tests/test_mcp_optimize.py tests/test_simulate_metrics.py -q
```

实验报告与结果：`../experiments/report/`、`../experiments/scheduling/results/`。
