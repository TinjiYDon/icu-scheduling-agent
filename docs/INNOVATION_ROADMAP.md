# 创新路线

> 本仓库独立演进；MCP 仅作为对外标准接口，不与其他 ICU 项目耦合。

## 目标

**可解释资源动态调度**：SOFA 临床评分 → 系统状态 → CP-SAT 求解 → 滚动时域更新。

## 里程碑

| 阶段 | 目标 | 交付物 | 状态 |
|------|------|--------|:--:|
| **P0** | Demo 跑通 | ETL + 合成SOFA + CP-SAT | ✅ |
| **P1** | 可解释 Demo | Streamlit 方案页 + 约束说明 | 🔄 |
| **P2** | 标准接口 | MCP Tool `optimize_beds(state)` | ⏳ |
| **P3** | 学习型策略 | PPO + 仿真环境 | ⏳ |
| **P4** | 多目标扩展 | 等待时间、负荷均衡等可插拔目标 | ⏳ |

> 注：P0 SOFA 目前使用合成数据（基于 stay_id 哈希），真实 MIMIC lab 评分待 Layer0 数据库就绪后替换。

## 当前重点

1. Streamlit 展示分配方案与滚动仿真结果
2. 连接 MIMIC 源库，替换合成 SOFA 为真实评分
3. MCP Tool schema（输入 state，输出 plan + explanation）
