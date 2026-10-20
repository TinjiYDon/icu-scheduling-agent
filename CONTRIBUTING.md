# 贡献指南

## 分层规则

```
L5 presentation  →  L4 application  →  L3 domain  →  L2 data_access  →  L1 infra
```

- Streamlit **禁止**直接 import `domain.optimizer`
- `domain/` **禁止**直接连库

## 合并门槛

```powershell
$env:PYTHONPATH = (Get-Location)
pytest tests/test_smoke.py tests/test_db.py tests/test_etl.py -q
# 若改仿真：pytest tests/test_simulate.py -q（存在时）
```

## Pull Request / Issue

- 模板：`.github/pull_request_template.md`
- 标签：`data` `algo` `app` `ui` `infra` `bug` `blocked`
