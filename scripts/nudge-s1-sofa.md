## 催促 · SOFA / 仿真指标（A + B）

### 人读摘要

| 项 | 内容 |
|----|------|
| Owner B | `#S1-1` SOFA 写入 `feat.sofa_*`；`#S2` simulate 指标完善 |
| Owner A | `#S1-2` ETL 含 labs；导出**非 schemas_only** Layer1 dump |
| C 已就绪 | L4 `plan` + Streamlit；PR #3 PPO **保持 Draft** |

### Agent 上下文

```text
入口：python -m application.simulate
文档：docs/PARAM_STORY.md · docs/BACKLOG.md
验收：pytest tests/test_plan.py -q；STATUS 写 SOFA/求解指标
RL：先补轨迹/feat，再谈 PPO（方案 B 底座）
```
