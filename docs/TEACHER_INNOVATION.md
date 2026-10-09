# 给老师的创新口径 · icu-scheduling-agent

> 2026-10-09 · 与桌面汇报 PPT 对齐 · 不宣称 online PPO  
> **口播脚本**：[DEMO_SCRIPT.md](DEMO_SCRIPT.md)（5–7 分钟 · 含多目标/对照页）

## 一句话

**骨干仍是 CP-SAT；加深的是同硬约束下三种多目标决策机理，以及压力场景与 Pareto 网格。**

## 不要这样讲

- 「我们用了 OR-Tools，所以算法新。」
- 把 PPO 训练曲线说成已在 MIMIC 床旁在线学习。
- 把一组 λ 的加权和说成已经解决多目标。

## 要这样讲

| 假设 | 相对谁 | 改了什么 | 证据文件 |
|------|--------|----------|----------|
| H4 | 只调一组权重 | 加权 / 词典序 / ε-约束 | `S2_MULTI_OBJECTIVE.md` · `STATUS.md` |
| 实验 | 口头宣称稳 | 六场景 + HV | `reports/moo/`（本地） |
| H3 对照 | 只展示 RL | **Fair 同池+同资源** CP-SAT / Greedy / PPO | `application/compare_policies.py` |
| S3 深化 | 单次对照 | 多 episode 同池抽样 + 同资源均值表 | `evaluate_ppo_benchmark` · 对照页 Tab |
| 优先级消融 | 只用 SOFA 或只信 GBDT | SOFA-only vs 公式 vs GBDT · Spearman / top-k | `reports/priority_ablation.json` |

## 演示台

按 [DEMO_SCRIPT.md](DEMO_SCRIPT.md) 顺序点导航：**项目 → 运行 → 多目标 → 对照 → 验收**。

Streamlit：**多目标**页（含当场 ε）· **对照**页（H3 单次 + 多 episode 深化）。  
`python -m application.compare_policies` → `reports/policy_comparison.json`  
`python -m application.evaluate_ppo_benchmark --episodes 3` → `reports/ppo_benchmark.json`  
`python -m application.run_moo_phase4 --split eval`  
`python -m application.compare_priority` → `reports/priority_ablation.json`
