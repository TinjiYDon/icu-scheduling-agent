# 方向同步（组员必读）· 2026-10-09

> Owner：`TinjiYDon` · 主线叙事：**先读** [MASTER_NARRATIVE.md](MASTER_NARRATIVE.md)  
> 已合入：PR #10–#15 → `main` · 在途学术补强见 PR #16  
> **S2-MOO = H4**；另有 H5 PtO · H6 滚动对照 · bake-off  
> 请 `git pull`；整合见 [INTEGRATION_PREP.md](INTEGRATION_PREP.md)。

## 人读摘要

| 项 | 内容 |
|----|------|
| **总目标** | 可审计 · 可对照 · 可滚动 的 ICU 分床（见 MASTER_NARRATIVE） |
| 定位 | **独立** 多目标多约束滚动床位调度 |
| 禁止 | 读 decision `risk_score`；无轨迹宣称 online PPO |
| 已采入 | **S2-MOO**（H4）· Fair H3 · H5/H6 · bake-off · 老师口径 |
| 勿混淆 | **MOO** ≠ **S2-TRAJ**；老师口径见 [TEACHER_INNOVATION.md](TEACHER_INNOVATION.md) |

## 验收命令

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m pytest tests/test_multiobjective.py tests/test_cp_sat_split.py -q
```

## 下一阶段

见 [ROADMAP.md](ROADMAP.md) · [TOP_TIER_NEXT.md](TOP_TIER_NEXT.md) · [INTEGRATION_PREP.md](INTEGRATION_PREP.md)

## Agent 上下文

```text
SSOT: docs/MASTER_NARRATIVE.md · docs/STATUS.md · docs/TEAM_DIRECTION.md
adopted: H4 MOO; H5 PtO; H6 rolling; fair H3; bake-off
next: merge PR#16; optional PPO zip smoke
禁区: dumps/ · decision risk_score · claim online PPO
```
