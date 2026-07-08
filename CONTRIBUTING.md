# 贡献指南

## 团队（3 人）

| 角色 | 职责 | 主要目录 |
|------|------|----------|
| **成员 A · 数据/基础设施** | ETL、migration、dump、环境脚本 | `domain/etl/` `migrations/` `scripts/` |
| **成员 B · 算法/优化** | SOFA、CP-SAT、PPO、仿真 | `domain/scoring/` `domain/optimizer/` |
| **成员 C · 应用/集成** | L4 用例、Streamlit、联调、**集成负责人** | `application/` `presentation/` `data_access/` |

详见 [`docs/COLLABORATION.md`](docs/COLLABORATION.md)

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
- 任务列表：[`docs/BACKLOG.md`](docs/BACKLOG.md)
- 标签：`data` `algo` `app` `ui` `infra` `bug` `blocked`
