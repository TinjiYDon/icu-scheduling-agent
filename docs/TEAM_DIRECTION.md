# 方向同步（组员必读）· 2026-09-24

> Owner：`TinjiYDon` · 已合入：PR [#10](https://github.com/TinjiYDon/icu-scheduling-agent/pull/10) · [#11](https://github.com/TinjiYDon/icu-scheduling-agent/pull/11) · [#12](https://github.com/TinjiYDon/icu-scheduling-agent/pull/12) → `main`  
> **S2-MOO 已正式采入为创新假设 H4**：[SOTA_SURVEY.md](SOTA_SURVEY.md) · [ROADMAP.md](ROADMAP.md)  
> 请 `git pull`；整合见 [INTEGRATION_PREP.md](INTEGRATION_PREP.md)。

## 人读摘要

| 项 | 内容 |
|----|------|
| 定位 | **独立** 多目标多约束滚动床位调度 |
| 禁止 | 读 decision `risk_score`；无轨迹宣称 online PPO |
| 已采入 | **S2-MOO**（Weighted / Lex / ε）· 阶段 5 UI · Fair H3 同资源 |
| 勿混淆 | **MOO 阶段 1–5** 与 **S2-TRAJ** 均已过；老师口径见 [TEACHER_INNOVATION.md](TEACHER_INNOVATION.md) |

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
next: S3 RL same-pool deepen; teacher demo on 多目标/对照
禁区: dumps/ · decision risk_score
```
