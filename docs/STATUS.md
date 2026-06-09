# 项目一 · 状态摘要

> 完整团队日志：`../PROJECT_STATUS.md`  
> **MIMIC**：下载中 · **阶段**：P0

## P0 目标

ETL → SOFA → CP-SAT → 滚动仿真 → Streamlit → Layer1 dump

## 本地命令

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

## 代码待办（MIMIC 后）

- [ ] `domain/scoring/sofa.py`
- [ ] `domain/optimizer/cp_sat.py`
- [ ] `domain/simulation/replay.py`
- [ ] PPO stub → 完整
