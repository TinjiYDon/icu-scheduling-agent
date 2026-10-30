# 成员 C · 集成负责人待办（2026-10-30 核对）

> 本机 `icu_scheduling` DB 已只读核对成功；PR #16 已合 main（`HEAD=34fe955`）。本次验收已回填，环境与分版本证据见 [ROADMAP_EXEC.md](ROADMAP_EXEC.md)，不据工程通过宣称研究充分验证。

## 已完成（本阶段）

| 任务 | 文件 | 状态 |
|------|------|------|
| L4 方案查询 | `application/plan.py` + `data_access/assignments_repo.py` | ✅ SQL 下沉 |
| Streamlit 演示 | `presentation/streamlit_app.py` | ✅ 目标分解 + 空态 |
| 测试 | `tests/test_plan.py` | ✅ smoke |

## 当前待完成

| 任务 | 说明 |
|------|------|
| 核心科学验证 | 逐患者临床时间顺序状态、独立留出与多种子验证未闭环；3 episode 抽样不自动构成独立留出 |
| 真实床旁轨迹 / 固定数据 offline RL | 尚未实现/交付；`train_ppo` 是仿真内交互训练，不消费导出包；临床训练证据仍缺 |

## 已关闭或已具备

| 任务 | 说明 |
|------|------|
| MCP `optimize_beds` | ✅ 骨架 · `python -m presentation.mcp_server` |
| Streamlit 集成 | ✅ 目标分解、滚动状态、多目标与 H3 对照页 |
| PPO 合成 smoke | ✅ 前轮 29 项无 DB 测试记录；新建合成模型短训/推理及接口验证，本组测试不验收现有 zip |
| 现有 PPO 检查点真跑冒烟 | ✅ 2026-10-30 `evaluate_ppo`；同池 20 人 + 20 床，三策略各 assigned=5、constraint_violations=0；当前报告与 flywheel 已生成 |
| PPO 3 episode benchmark | ✅ 同池同资源；三策略 mean_assigned=5、mean_high_risk_wait=15、mean_constraint_violations=0 |
| 轨迹协议 2.0 | ✅ 真跑 4 步 / 4 transitions；真实 JSON 连续性、人数守恒及 checked 且无违规已断言；非床旁事件日志 |
| 40 人 H5 / bake-off | ✅ 报告已生成；候选截断为 20 的问题已修复 |
| H6 最终验收 | 2026-10-30 共享初态并保留在院患者，8 步 rolling/greedy 期末均 18，均无违约，本设定打平 |
| 多目标复验 | ✅ eval 六场景 18 个 OPTIMAL；阶段 3 新结果 27/17/3/HV=0.052130，历史结果不覆盖 |
| 本次测试 / 依赖 | ✅ 最终 pytest 217 passed / 6 skipped；另只读 DB 3 passed；ETL 写数据测试未运行，`scikit-learn` 已补入依赖 |
| 两项独立复核边界修复 | ✅ 默认 `retain_occupied=True`，CP 强制在院患者分配且检查返回不丢人；仅显式 `False` 允许 legacy 退队列。CP/RL 仅真正隔离患者在 ISO 床豁免错配，其他非偏好分配（含偏好科室不存在）计错配；回归与最终重跑均通过 |
| Bugbot | ✅ 已开 · `docs/BUGBOT.md` |

`hybrid` 在 `application/optimize.py` 中明确预留，属于可选扩展，不是必做缺陷。工程功能已具备与研究充分验证分别验收；当前报告及轨迹包仍不入 Git。

## 验证入口（列出不代表本次已通过）

```powershell
$env:PYTHONPATH = (Get-Location)
python -m application.simulate
python -m application.run_p0
streamlit run presentation/streamlit_app.py
pytest tests/test_plan.py -q
```
