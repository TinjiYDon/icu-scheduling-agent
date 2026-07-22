## C · S4 MCP 骨架已合

### 人读摘要

| 项 | 内容 |
|----|------|
| Owner | C |
| 工具 | `optimize_beds(run_id?)` |
| 路径 | `presentation/mcp_tools.py` · `presentation/mcp_server.py` |

### Agent 上下文

```text
验收：pytest tests/test_mcp_optimize.py -q
启动：pip install 'mcp>=1.0' && python -m presentation.mcp_server
无 run_id → run_simulation_with_plan()；有 run_id → get_plan()
```
