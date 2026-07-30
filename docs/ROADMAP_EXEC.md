# 执行路线图 ROADMAP_EXEC（人机双可读）

> 更新：2026-07-25 · Wave1 calib/eval 骨架 · Wave2 等 B SOFA 数值 · PPO 不合 main

## 人读摘要

| Wave | 含义 | 状态 | 主责 |
|------|------|------|------|
| **1** | calib/eval 协议 + simulate `metrics` | ✅ 骨架 | C |
| **2** | SOFA→feat + STATUS 数字 | ⏳ 等 B/A | B |
| **PPO** | Draft PR #3 | 保持 Draft | B |

| 划分 | 名称 | 规则 |
|------|------|------|
| 70% / 30% | **calib / eval** | seed=42；eval 只评估不回写调参 |

## Agent 上下文

```text
配置：configs/optimizer.yaml → eval_split
代码：domain/optimizer/eval_split.py · application/simulate.py metrics
验收：pytest tests/test_simulate_metrics.py tests/test_plan.py -q
仿真：python -m application.simulate
禁止：在 eval 集上调 lambda；宣称 schemas_only dump 可训 PPO
Wave1 注：assignment 仍可跑全量；Wave2 应由 B 按 calib/eval 子集限制求解
```

## Wave2 等待清单

- [ ] B：SOFA 写入 feat + simulate 指标入 STATUS（#4）— **或 Owner 代跑 sofa 后 B 填指标**
- [ ] A：labs/完整 dump（#5）— Layer0 含 labevents 即可；Owner 可代导出

## Owner 可代备（SOFA / CP-SAT · ≠ 真 PPO）

```powershell
$env:PYTHONPATH = (Get-Location)
# Layer0 DSN 指向含 mimiciv_hosp.labevents 的库
.\.venv\Scripts\python.exe -c "from domain.scoring.sofa import compute_sofa_timeseries; print(compute_sofa_timeseries())"
.\.venv\Scripts\python.exe -m application.simulate
.\scripts\export_layer1.ps1 -MimicSource mimic
```

| 代备项 | 能支撑 | 不能支撑 |
|--------|--------|----------|
| labs→`feat.sofa_timeseries` + priority | CP-SAT / plan 演示、Wave2 指标 | — |
| 完整 Layer1 dump | A/B 复现 | — |
| Draft PR#3 合成 env smoke | PPO **冒烟** | **online / 全量真实 PPO**（需 `sim` 轨迹 + 审查合入） |

**PPO 边界**：准备好 labs/SOFA/feat **方便 B 做优化与对比**，但**不等于**已为 PPO 备好训练轨迹。真 PPO 仍走 Draft PR #3，不合 main 直至数据与审查通过。
