# 创新路线 — ICU 调度智能体

> 与决策、多模态项目**独立仓库、独立数据库**；CP-SAT 硬约束 + 可解释目标分解，后期 MCP 暴露。

## 总叙事

**可解释资源动态调度**：SOFA 临床评分 → 系统状态 → OR-Tools CP-SAT 求解 → 滚动时域更新。

## 分步里程碑

| 阶段 | 目标 | 交付物 | 依赖 |
|------|------|--------|------|
| **P0** ✓ | Demo 跑通 | ETL + SOFA + CP-SAT 20 床分配 | mimic_iv_demo |
| **P1** | 可解释 Demo | Streamlit 方案页 + 约束/目标分解说明 | P0 |
| **P2** | 标准接口 | MCP Tool `optimize_beds(state)` 返回 plan + explanation | P1 |
| **P3** | 学习型策略 | PPO stub → 仿真环境联调 | SimPy 仿真 |
| **P4** | 软约束融合（可选） | 消费决策 MCP 的 risk_score 作为优先级权重 | 决策 P2 |

## 后期扩展空间

- **与决策协同**：仅通过 MCP/消息，**禁止**跨库 SQL；符合现有架构边界
- **多目标扩展**：等待时间、负荷均衡、转运成本可插拔进 CP-SAT 目标函数
- **CDN/边缘**：调度服务容器化后，静态配置（`configs/optimizer.yaml`）可 CDN 缓存

## 当前 Next

1. Streamlit 展示分配方案与 SOFA 分布
2. 与决策项目对齐 MCP JSON schema（并行 P2）

## 关联仓库

- 决策：[`icu-decision-agent`](https://github.com/TinjiYDon/icu-decision-agent)
- 多模态：[`zhixue-multimodal`](https://github.com/TinjiYDon/zhixue-multimodal)
