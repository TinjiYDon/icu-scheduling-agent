# 三人协作手册 · icu-scheduling-agent

> 独立仓库。与 icu-decision-agent **无代码依赖**。

## 1. 角色

| 成员 | 角色 | 目录 | 入口 |
|------|------|------|------|
| **A** | 数据/基础设施 | `domain/etl/` `migrations/` `scripts/` | `run_data_pipeline.ps1` |
| **B** | 算法/优化 | `domain/scoring/` `domain/optimizer/` | `application/simulate.py` |
| **C** | 应用/集成负责人 | `application/` `presentation/` `data_access/` | `application/run_p0.py` |

## 2. 集成负责人（C）

- 合并 PR、维护 [`STATUS.md`](STATUS.md)
- 裁定 L4 接口（如 `run_simulation(state) -> plan`）

## 3. 垂直切片

| Sprint | 切片 | 主责 | 验收 |
|--------|------|------|------|
| S0 ✓ | 数据检查点 | A | `run_data_pipeline.ps1` |
| S1 | SOFA 写入 feat | B | staging→feat 可查 |
| S2 | CP-SAT 20 床 | B | `simulate` 输出方案 |
| S3 | Streamlit 方案页 | C | 展示分配+约束说明 |
| S4 | PPO / MCP | B+C | 路线图 P2+ |

详见 [`BACKLOG.md`](BACKLOG.md)

## 4. 契约

| 类型 | 位置 |
|------|------|
| 表结构 | `migrations/`（A） |
| 优化器配置 | `configs/optimizer.yaml.example`（B 提议，C 合并） |
| 仿真输出 | L4 返回 plan + metrics JSON（C 定义，B 填充） |

## 5. 周会（15 分钟）

进度 → blocked → 下周切片 → 开 issue

## 6. 调试

| 现象 | 先找 |
|------|------|
| ETL | A |
| SOFA/CP-SAT 不可行 | B |
| UI 无数据 | C → L4 |
