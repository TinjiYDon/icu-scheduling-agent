# Dump 交付说明（队友 restore）

> 更新：2026-08-02 · **不入 GitHub** · 线下单发

## 单发文件（Owner → 队友）

| 文件 | 绝对路径 | 说明 |
|------|----------|------|
| **主 dump** | `d:\project\icu-scheduling-agent\dumps\icu_scheduling_P0-full_mimic_94458stays_20260802.dump` | SOFA + staging · CP-SAT / 滚动仿真 |
| 元数据（可选） | `d:\project\icu-scheduling-agent\dumps\DATA_VERSION_20260802_1758.json` | SHA / 行数 |

**SHA-256**：`cb72a741c0f3d092a8e4ed661a16dd64c0787833725abfdd59ba1c036c2c8294`  
旧 20260727 dump 已从本机清理。

## 恢复 + Ops 台

```powershell
cd d:\project\icu-scheduling-agent
.\scripts\restore_layer1.ps1 -DumpFile .\dumps\icu_scheduling_P0-full_mimic_94458stays_20260802.dump
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m streamlit run presentation/streamlit_app.py --server.port 8502
```

验收：`staging.icustays` / `feat.sofa_timeseries` ≈ **94458**；Ops 页 Run → solver OPTIMAL。

## 禁止

- schemas_only / 过时 dump  
- 宣称含 online PPO 轨迹或 Layer0 labevents  
- 把 dump 推进 GitHub  
