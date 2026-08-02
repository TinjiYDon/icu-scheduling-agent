# 答辩演示口播（3–5 分钟）

> 启动：`.\scripts\run_console.ps1` → http://localhost:8502  
> 前置：已 restore scheduling P0 dump；默认策略 **cp_sat**（勿宣称在线 PPO）

## 流程

1. **项目（总览）**（约 40s）  
   - 滚动时域床位分配：优先级等待 / 超负荷 / 均衡 / zone 匹配。  
   - 配置床位约 20；明确 **默认 CP-SAT**。

2. **运行**（约 2.5min）  
   - 首次进入会 **自动跑一次**（侧栏可关）。  
   - KPI：求解状态、占用/利用率、**高危分配率**、**Zone 匹配率**。  
   - 占用时序 / 热力 / SOFA；分配表按高 SOFA 排序。  
   - 侧栏或 expander 读 **可解释报告**（目标分解 + 前几条分配理由）。

3. **验收**（约 1min）  
   - 对照会话内仿真指标与门禁说明。  
   - 收尾：PPO 代码在仓内，但 **无 MIMIC 在线轨迹时不宣称 online RL**。

## 一键启动

```powershell
cd d:\project\icu-scheduling-agent
.\scripts\run_console.ps1
```
