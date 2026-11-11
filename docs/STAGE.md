# STAGE（scheduling 阶段门禁）

> 项目：icu-scheduling-agent｜当前阶段：S4（结论与成稿）｜更新：2026-11-11
> 规则：不跨阶段开工；旧阶段文档进 `docs/archive/`，不删。

| 阶段 | 目标 | 产出 | Exit 条件 | 状态 |
|---|---|---|---|---|
| S0 问题定义 | 分床问题一句话 + 不做什么 | `docs/BRIEF.md` L0/L1 | 3 个反例写清 | ✅ |
| S1 证据底座 | 数据/字段审计 | 三条实证发现 | 数字可复核 | ✅ |
| S2 方法原型 | CP-SAT + ε 网格 + 合成 smoke | 代码 + 单测 + demo | 单测绿 + smoke | ✅ |
| S3 真实数据 | MIMIC 网格 + B_pool | `reports/aigc/mimic_grid.json` | F1 确认 + 预检通过 | ✅ |
| S4 结论成稿 | 正常负载 + 前沿质量 + 四张表 | 报告/论文 | 正常负载 assigned 15–20；前沿 ≥20 点或给出瓶颈证据 | 🔄 |

## 门禁

```powershell
.\.venv\Scripts\python.exe C:\Users\lenovo\.dsh\skills\complex-project-harness\scripts\preflight.py --config preflight.yaml
```

## 当前证据

- S1：隔离启发式 76,157/94,458；top-20 中 19/20 需隔离；priority ≡ 1+SOFA/10（corr=1.0）；`los_hours` 实为天。
- S2：DAC/FD/B_pool/H10 单测；ε 网格 smoke 可复跑。
- S3：6 场景 × 5 seed 真实网格（`reports/aigc/mimic_grid.json`）；B_pool 仅 `small_pool` 非零（−0.004864）。
- S4 未完成：汇报口径统一、四张证据表、README 索引补遗。

## 阶段变更

| 日期 | 从 | 到 | 依据 |
|---|---|---|---|
| 2026-11-03 | S3 | S4 | 真实网格 + B_pool 跑完 |
| 2026-11-11 | S4 | S4（口径修订） | HV–churn 工程链路打通；主目标改为“正常负载 + 前沿质量”后再谈论文 |
