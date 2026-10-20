# Dump 交付说明（队友 restore）

> **不入 GitHub** · 线下单发

## 单发文件（Owner → 队友）

| 文件 | 路径 | 说明 |
|------|------|------|
| **主 dump** | `dumps/icu_scheduling_P0-full_<source>_<stays>stays_<yyyymmdd>.dump` | SOFA + staging · CP-SAT / 滚动仿真 |
| 元数据（可选） | `dumps/DATA_VERSION_<version>.json` | 行数 / 来源 / 导出时间 |

当前本地副本：`dumps/icu_scheduling_P0-full_mimic_94458stays_20260727.dump`  
**SHA-256**：`7df1e4655c9e5742568ce34a55239c95cc7dc6154a7f2477203e05a5eba503a6`

## 恢复 + 校验

```powershell
.\scripts\restore_layer1.ps1 -DumpFile .\dumps\icu_scheduling_P0-full_mimic_94458stays_20260727.dump
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m application.simulate
```

- 未安装宿主 `pg_restore` 时，脚本自动改用 `docker exec`（需 `icu_scheduling_pg16` 容器在运行；`dumps/` 已挂载为 `/dumps`）。
- 目标库默认 `icu_scheduling`，可用 `-Database <name>` 恢复到他库；端口按 `configs/database.yaml` 解析。

验收：`staging.icustays` / `feat.sofa_timeseries` ≈ **94458**；`application.simulate` 返回 `solver_status=OPTIMAL`。

## 禁止

- schemas_only / 过时 dump  
- 宣称含 online PPO 轨迹或 Layer0 labevents  
- 把 dump 推进 GitHub  
