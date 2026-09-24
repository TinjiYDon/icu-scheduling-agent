# 代码整合与完善准备清单 · scheduling

> 2026-09-24 · Owner：`TinjiYDon` · 前置：S2-MOO 已采入 ROADMAP

## 已就绪

| 模块 | 路径提示 |
|------|----------|
| S2-MOO | `domain/optimizer/multiobjective.py` · `cp_sat.py` · `docs/S2_MULTI_OBJECTIVE.md` |
| 测试 | `tests/test_multiobjective.py` |
| 约束 / 飞轮骨架 | `configs/constraint_rules.yaml` · `reports/flywheel/` |

## 整合顺序

1. `git pull origin main`  
2. restore scheduling dump（见 `DUMP_READY.md`）  
3. `pytest tests/test_multiobjective.py tests/test_cp_sat_split.py tests/test_lambda_weights.py -q`  
4. 冒烟：`run_assignment(objective_mode="weighted_sum"|"lexicographic"|"epsilon_constraint")`（calib）  
5. **下一拍二选一做透**：S2-TRAJ 导出 **或** MOO 阶段 2 指标语义  

## 完善缺口

| ID | 项 | 状态 |
|----|----|------|
| C1 | S2-TRAJ 导出验收对照 `TRAJECTORY_PROTOCOL.md` | ✅ 2026-09-24 |
| C2 | MOO 阶段 2：wait/overload 语义 | ✅ 2026-09-24（acuity overload） |
| C3 | STATUS 写入三模式对照表（真数） | 待本机（阶段 3/4） |
| C4 | Streamlit 三模式 UI | P2 |

## 禁区

- 读取 decision `risk_score`  
- 无轨迹宣称 online PPO  
- dumps/ artifacts/ 入 Git  
