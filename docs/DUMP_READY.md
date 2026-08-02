# Dump 交付说明（队友 restore）

> 更新：2026-07-27 · **dump 不入 GitHub**

## 人读摘要

| 文件 | schemas_only | 可用于 |
|------|--------------|--------|
| `icu_scheduling_P0-full_mimic_94458stays_20260727.dump` | **false** | ✅ SOFA + staging + CP-SAT 演示 |
| `…20260708…`（若仍存在） | true / 过时 | ❌ 勿用 |

| 需求 | dump 是否够 |
|------|-------------|
| CP-SAT / plan / Streamlit | ✅ |
| 用已写入的 `feat.sofa_timeseries` | ✅ |
| 从零重算 SOFA（需 Layer0 labevents） | 需本机 `mimic` labs 或向 Owner 要 Layer0 说明 |
| online PPO 轨迹 | ❌ 本地无轨迹包 → `docs/PPO_SMOKE.md` |

```powershell
.\scripts\restore_layer1.ps1 -DumpFile .\dumps\icu_scheduling_P0-full_mimic_94458stays_20260727.dump
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m application.simulate
```
