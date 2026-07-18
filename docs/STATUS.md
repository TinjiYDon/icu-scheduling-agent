# 项目状态

> 更新：2026-07-14

## 数据检查点（已完成）

| 项 | 状态 |
|----|------|
| ETL staging | ✓ 94,458 stays |
| dump | ✓ `dumps/icu_scheduling_P0-etl_mimic_94458stays_20260708.dump` |
| 冒烟测试 | ✓ `tests/test_smoke.py` |

## 仿真阶段（进行中）

| 项 | 状态 | 说明 |
|----|------|------|
| CP-SAT 基础模型 | ✅ 完成 | 200 候选 → 20 床，OPTIMAL |
| CP-SAT 多目标 | ✅ 完成 | f₁ 等待 + f₂ 超负荷 + f₃ 均衡 + f₄ 科室匹配 |
| CP-SAT 约束 | ✅ 完成 | 隔离床 4 张 + 呼吸机 ≤8 + 科室偏好 |
| SOFA 评分（合成） | ✅ 完成 | 全量 94K 患者，8 秒生成 |
| SOFA 评分（真实） | ⏳ 待 MIMIC | 需 Layer0 源库连接 |
| 可解释输出 | ✅ 完成 | `domain/optimizer/explain.py` |
| 滚动时域仿真 | ✅ 完成 | `domain/rolling/engine.py`，24h 仿真 |
| L4 `plan.get_plan` / `run_simulation_with_plan` | ✅ C 完成 | `application/plan.py` |
| Streamlit 面板 | ✅ C 完成 | `presentation/streamlit_app.py` |
| PPO / MCP | ⏳ P2+ | 远期规划 |

## 成员 C 本阶段交付

- `application/plan.py` + `data_access/assignments_repo.py`
- `presentation/streamlit_app.py`（目标分解 + 空态/not_found）

## 测试环境

| 组件 | 配置 |
|------|------|
| PostgreSQL 16 | Docker 容器，端口 `localhost:5434` |
| Python | 3.12.10，虚拟环境 `.venv` |
| 依赖 | sqlalchemy / psycopg / polars / pandas / ortools / streamlit |

## 验证

```powershell
.\.venv\Scripts\Activate.ps1
pytest tests/test_plan.py tests/test_smoke.py -q

# CP-SAT 单次求解 + 解释报告
python -c "from domain.optimizer.cp_sat import run_assignment; from domain.optimizer.explain import explain_assignment; print(explain_assignment(run_assignment()))"

# 滚动时域仿真（24h）
python -m application.simulate

# Streamlit
streamlit run presentation/streamlit_app.py
```

## 2026-07-19 · λ 调参与 PPO 策略开发

### 本次新增

- CP-SAT 四个 λ 权重均已配置化，支持单次覆盖、合法性校验和独立业务评价指标。
- 新增 `domain/optimizer/tuning.py`、`scripts/tune_lambda.py` 和 `docs/LAMBDA_TUNING.md`，支持快速/完整网格搜索、CSV、Pareto 前沿和推荐 JSON。
- λ 实验调用 `run_assignment(..., persist=False)`，不会把调参方案写入正式 `sched.assignments`；正常求解仍默认持久化。
- 新增 Gymnasium `ICUEnv`：固定状态向量、逐患者床位动作、等待动作、合法动作 mask 和奖励分解。
- PPO 呼吸机约束与 CP-SAT 对齐为全局容量；隔离/呼吸机需求暂时沿用项目现有的确定性模拟规则。
- 新增 PostgreSQL → PPO 的 `Patient` / `Bed` 数据适配器及配置化环境工厂。
- 训练环境从 200 名候选池按 seed 抽取 20 人 episode，避免只记忆固定患者顺序；推理使用确定性快照。
- 新增 MaskablePPO 训练、保存、加载与推理入口：`application.train_ppo`、`application.run_ppo`。
- 新增统一 `cp_sat|ppo|hybrid` 策略入口；`hybrid` 目前只保留接口并明确返回未实现。
- 新增 PPO、贪心、CP-SAT 评估入口，报告输出到 `reports/ppo_evaluation.json`。
- `pyproject.toml` 新增 `gymnasium`、`stable-baselines3`、`sb3-contrib` 依赖。
- 新增 λ、PPO 环境、数据适配、推理、评估和策略选择测试代码。

### 当前状态与限制

- λ 调参执行器已完成，但尚未实际生成实验 CSV，因此当前 λ 仍是基线值，不能称为最优参数。
- PPO 训练与推理代码已完成，但尚未训练出模型，也没有 PPO 与 CP-SAT 的留出场景对比报告。
- 当前机器 Python 安装损坏、`.venv` 尚未创建，本次新增测试和训练命令均未执行。
- staging 表没有真实隔离/呼吸机需求字段，目前仍使用模拟属性。
- 默认策略继续保持 `cp_sat`，PPO 完成训练和验收前不切换。
- 本轮仅完成 `git diff --check` 静态检查。

### 环境恢复后的验证顺序

```powershell
pip install -e ".[dev]"

pytest tests/test_lambda_weights.py tests/test_lambda_tuning.py -q
pytest tests/test_rl_env.py tests/test_rl_data_adapter.py -q
pytest tests/test_rl_policy.py tests/test_rl_evaluation.py -q
pytest tests/test_optimize_policy.py -q

# λ 快速实验（16 组）与完整实验（256 组）
python scripts/tune_lambda.py --quick
python scripts/tune_lambda.py

# PPO 训练、推理与基线评估
python -m application.train_ppo
python -m application.run_ppo
python -m application.evaluate_ppo
```
