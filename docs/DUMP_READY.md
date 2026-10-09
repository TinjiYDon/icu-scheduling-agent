# Dump 交付说明（队友 restore）

> 更新：2026-10-09 · **不入 GitHub** · 线下单发 / 本机旁路目录

## 本机主路径（当前）

| 文件 | 绝对路径 | 说明 |
|------|----------|------|
| **主 dump（scheduling）** | `C:\Users\lenovo\Desktop\decision shcedule\dump\icu_scheduling_P0-full_mimic_94458stays_20260802.dump` | SOFA + staging · CP-SAT / 滚动仿真 |
| decision dump（勿用于本仓） | `C:\Users\lenovo\Desktop\decision shcedule\dump\icu_decision_S2-full_mimic_94458stays_20260802.dump` | **另一库**；本仓 restore **禁止**用它 |

仓库内 `dumps/` 可为空（gitignored）；restore 时直接传绝对路径即可。

**SHA-256**（历史 Owner 记录）：`cb72a741c0f3d092a8e4ed661a16dd64c0787833725abfdd59ba1c036c2c8294`

## 恢复 + Ops 台

```powershell
cd "C:\Users\lenovo\Desktop\decision shcedule\icu-scheduling-agent"
.\scripts\restore_layer1.ps1 -DumpFile "C:\Users\lenovo\Desktop\decision shcedule\dump\icu_scheduling_P0-full_mimic_94458stays_20260802.dump"
$env:PYTHONPATH = (Get-Location)
# 有 venv 时优先：
.\.venv\Scripts\python.exe -m streamlit run presentation/streamlit_app.py --server.port 8502
```

验收：`staging.icustays` / `feat.sofa_timeseries` ≈ **94458**；Ops 页 Run → solver OPTIMAL；「多目标」「对照」页可点。

## 禁止

- schemas_only / 过时 dump  
- 用 **decision** dump restore 进 `icu_scheduling`  
- 宣称含 online PPO 轨迹或 Layer0 labevents  
- 把 dump 推进 GitHub  
