# 方向同步（组员必读）· 2026-09-24

> Owner：`TinjiYDon` · 已合入：PR [#10](https://github.com/TinjiYDon/icu-scheduling-agent/pull/10) → `main`  
> **S2-MOO 已正式采入为创新假设 H4**：[SOTA_SURVEY.md](SOTA_SURVEY.md) · [ROADMAP.md](ROADMAP.md)  
> 请 `git pull`；整合见 [INTEGRATION_PREP.md](INTEGRATION_PREP.md)。

## 人读摘要

| 项 | 内容 |
|----|------|
| 定位 | **独立** 多目标多约束滚动床位调度 |
| 禁止 | 读 decision `risk_score`；无轨迹宣称 online PPO |
| 已采入 | **S2-MOO**（Weighted / Lex / ε） |
| 勿混淆 | **S2-TRAJ** 与 **MOO 阶段 2–3** 均已过；下一 P0 = **MOO 阶段 4 六场景** |

## 验收命令

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m pytest tests/test_multiobjective.py tests/test_cp_sat_split.py -q
```

## 下一阶段

见 [ROADMAP.md](ROADMAP.md) · [TOP_TIER_NEXT.md](TOP_TIER_NEXT.md) · [INTEGRATION_PREP.md](INTEGRATION_PREP.md)

## Agent 上下文

```text
SSOT: docs/STATUS.md · docs/TEAM_DIRECTION.md · docs/S2_MULTI_OBJECTIVE.md
adopted: S2-MOO = H4
next: MOO phase4 six-scenario pack
禁区: dumps/ · decision risk_score
```
