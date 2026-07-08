# 创新路线

> 本仓库独立演进；MCP 仅作为对外标准接口，不与其他 ICU 项目耦合。

## 目标

**可解释资源动态调度**：SOFA 临床评分 → 系统状态 → CP-SAT 求解 → 滚动时域更新。

## 里程碑

| 阶段 | 目标 | 交付物 |
|------|------|--------|
| **P0** ✓ | Demo 跑通 | ETL + SOFA + CP-SAT |
| **P1** | 可解释 Demo | Streamlit 方案页 + 约束说明 |
| **P2** | 标准接口 | MCP Tool `optimize_beds(state)` |
| **P3** | 学习型策略 | PPO + 仿真环境 |
| **P4** | 多目标扩展 | 等待时间、负荷均衡等可插拔目标 |

## 扩展方向

- **MCP**：对外暴露 `optimize_beds`，供任意 Agent 客户端调用
- **容器化**：调度服务 + 配置热更新

## 当前重点

1. Streamlit 展示分配方案与 SOFA 分布
2. MCP Tool schema（输入 state，输出 plan + explanation）
