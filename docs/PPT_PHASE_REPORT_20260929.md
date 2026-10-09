# ICU Scheduling Agent · 阶段性汇报大纲

> 受众：项目组 / 答辩预演 · 语言：中文 · 建议 10–12 页  
> 素材：`docs/STATUS.md` · `docs/PHASE_PROGRESS_20260929.md` · `reports/moo/`  
> 导出：可用 OpenClaw `/ppt` 或本地工具转 `.pptx`（本文件为大纲，非 pptx 二进制）

## 1. 封面
- 标题：ICU 调度——创新不在「又调用了 CP-SAT」
- 副题：H4 三种多目标机理 · 六场景 · 轨迹协议边界
- 日期：2026-09-29

## 2. 问题与定位
- ICU 床位：隔离 / 呼吸机 / 分区匹配硬约束
- **独立运筹项目**；不读 decision 风险分
- 默认求解器：CP-SAT

## 3. 创新假设 H4（S2-MOO）
- 同硬约束下对照：Weighted Sum / Lexicographic / ε-Constraint
- 回答：权重敏感？词典序能否保证优先级？ε 能否给 Pareto 候选？

## 4. 方法架构
- 决策变量与硬约束固定；只换多目标机理
- 目标：occupancy / high_risk / wait(=priority_served) / overload(acuity) / …

## 5. 阶段 2 语义校正
- wait ≠ 真实等待时长 → priority_served
- overload = SOFA≥10 落非隔离床（acuity 错配）

## 6. 阶段 3：payoff + ε 网格
- A2：81 点 · 可行 54 · 非支配 4 · HV=0.038794
- 基线：WS wait=57937 · Lex wait=58892 / high_risk=12

## 7. 阶段 4：六压力场景
- 正常 / 床不足 / 隔离不足 / 呼吸机不足 / 高 SOFA / 科室不均
- WS+Lex 六场景均 OPTIMAL（表：见 STATUS）

## 8. 场景对照表（一页表）
- 贴 S1–S6 的 assigned / wait / high_risk

## 9. 轨迹协议 S2-TRAJ
- 离线滚动导出 · 协议 1.0
- **明确边界**：不宣称 online MIMIC-PPO

## 10. 合入与工程
- PR#10 MOO · 阶段 2–4 落 main · open PR=0
- dumps/reports 不入 Git

## 11. 局限与下一步
- 中位 ε 在压力场景可能不可行
- 下一拍：Streamlit 三模式 UI

## 12. Q&A
- 预留
