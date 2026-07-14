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
| CP-SAT 多目标 | ✅ 完成 | f₁ 等待 + f₂ 超负荷 + f₃ 均衡 |
| CP-SAT 约束 | ✅ 完成 | 隔离床 4 张 + 呼吸机 ≤8 + 科室偏好 |
| SOFA 评分（合成） | ✅ 完成 | 全量 94K 患者，8 秒生成 |
| SOFA 评分（真实） | ⏳ 待 MIMIC | 需 Layer0 源库连接 |
| 可解释输出 | ✅ 完成 | `domain/optimizer/explain.py` |
| 滚动时域仿真 | ✅ 完成 | `domain/rolling/engine.py`，24h 仿真 |
| Streamlit 面板 | ⏳ 占位 | `presentation/streamlit_app.py` |

## 测试环境

| 组件 | 配置 |
|------|------|
| PostgreSQL 16 | Docker 容器，端口 `localhost:5434` |
| Python | 3.12.10，虚拟环境 `.venv` |
| 依赖 | sqlalchemy / psycopg / polars / pandas / ortools / streamlit |

## 运行命令

```powershell
.\.venv\Scripts\Activate.ps1

# CP-SAT 单次求解 + 解释报告
python -c "from domain.optimizer.cp_sat import run_assignment; from domain.optimizer.explain import explain_assignment; print(explain_assignment(run_assignment()))"

# 滚动时域仿真（24h）
python -m application.simulate
```
