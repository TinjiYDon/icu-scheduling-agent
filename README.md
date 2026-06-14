# ICU 医疗资源动态调度智能体

项目一 · 仓库 `icu-scheduling-agent` · PostgreSQL `icu_scheduling`

## 方案与状态

- **当前进度**：`docs/STATUS.md`
- **队友恢复 dump**：见下方「Docker + restore」

## 队友：Docker + restore

```powershell
docker compose up -d
.\scripts\restore_layer1.ps1 -Target scheduling -DumpFile .\dumps\icu_scheduling_layer1_schemas_xxx.dump
copy configs\data.yaml.example configs\data.yaml
pytest tests/ -q
python -m application.run_p0
```

## 快速开始

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -e ".[dev]"
copy .env.example .env
copy configs\database.yaml.example configs\database.yaml
copy configs\data.yaml.example configs\data.yaml
.\scripts\apply_migrations.ps1
pytest tests/ -q
python -m application.etl_pipeline
streamlit run presentation/streamlit_app.py
```

## 架构

L5 Streamlit → L4 application → L3 domain (SOFA / CP-SAT / PPO) → L2 data_access → L1 infra → PostgreSQL
