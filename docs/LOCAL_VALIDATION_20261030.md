# 本地待办完成与改进记录（2026-10-30）

## 修复内容

1. **测试入口与 CI**：数据库集成测试改为 `--run-db` 显式开启；移除 `test_cp_sat_quick.py` 加载即访问数据库的行为，改为对真实 CP-SAT 模型的只读测试。CI 从 8 个白名单文件扩大到完整无数据库测试。
2. **滚动人数与状态**：零入出院率保持为零；使用独立随机数实例；同优先级按 `stay_id` 排序。默认 `retain_occupied=True`，在院患者未经出院不能被优化器移除，CP 模型与返回结果均检查此条件。仅显式关闭该选项时允许旧研究行为，此时按原始特征回队列并分别记账，逐步检查人数守恒。
3. **滚动硬约束与回退**：贪心也检查隔离与全局呼吸机容量，所有 CP-SAT 输出在应用前验证患者/床位唯一性、床位范围和资源约束。CP-SAT 未返回可行解时保留已验证的在床患者，记录 `FALLBACK`。新入院上限通过 `max_new_admissions` 进入 CP-SAT 模型。
4. **H6 对照起点**：两种策略复用同一初始床位分配，避免分别求初始解造成差异；报告披露后续出院患者身份仍会随策略状态分歧而不同。
5. **PPO / 贪心口径**：普通患者可使用空闲隔离床，与 CP-SAT 一致；床旁具备便携呼吸机不再消除普通床的高危错配惩罚。科室错配仅对有隔离需求且入住 ISO 床的患者豁免；普通患者落 ISO 床及偏好科室不存在均按实际错配计数，CP/RL 同步。原检查点可以加载复验，但新规则不代表旧训练过程已被重新验证。
6. **实验候选规模**：新增环境候选数覆盖参数，修复 H5 与 bake-off 即使指定 40 人仍被默认 20 人环境截断的问题，补充回归测试。
7. **GBDT 依赖与报错**：将实际使用的 `scikit-learn` 加入安装依赖；只有 LightGBM 无法导入时才选后备实现，训练数据/训练过程错误直接暴露。
8. **轨迹协议 2.0**：导出明确 `persist=False`，关闭数据库写入；校验步数、文件名和输出目录。`state` 使用转移前状态，新增 `next_state`。约束缺少检查时为 `null`，奖励中的 `wait` 仅为空床代理，包内明确披露；迁移说明见 [TRAJECTORY_PROTOCOL.md](TRAJECTORY_PROTOCOL.md)。
9. **待办文档**：修正 PR #16 尚未合并、现有检查点尚未验收、DB 未启动等过期或错误判断。合成模型 smoke、原 zip 推理复验、仿真轨迹、固定数据 offline RL 分别列明。

## 验证结果

本机数据库为 `icu_scheduling`，`staging.icustays`、`feat.sofa_timeseries`、`feat.patient_priority` 均为 94,458 行。本次实验均只读数据库，报告和轨迹保存在被 Git 忽略的本地目录。

| 验证 | 命令 / 范围 | 结果 |
|------|-------------|------|
| 完整普通测试 | `python -m pytest -q` | 217 passed，6 skipped；4 项集成测试需 opt-in，2 项符号链接测试因 Windows 权限跳过 |
| 数据库只读集成 | `pytest tests/test_cp_sat_quick.py tests/test_db.py --run-db -q` | 3 passed |
| 现有 PPO zip | `python -m application.evaluate_ppo` | 20 人同池同资源，PPO / Greedy / CP-SAT 各分配 5 人，均无约束违反 |
| PPO benchmark | `python -m application.evaluate_ppo_benchmark --episodes 3` | 三策略 mean assigned 均为 5，mean high_risk_wait 均为 15，均无约束违反 |
| 方法 bake-off | `python -m application.run_method_bakeoff --candidate-patients 40 --max-time 20` | 实际 40 人，贪心及 WS / Lex / ε / RFCC 均分配 5 人；4 个 CP 模式均 OPTIMAL |
| H5 | `python -m application.run_pto_ablation --candidate-patients 40 --max-time 20` | SOFA-only / 公式 / GBDT 各分配 5 人；相对公式 Jaccard 分别 0.1111 / 1 / 1 |
| H6 | `python -m application.run_rolling_contrast --steps 8` | 共享初始分配，默认保留在院患者；期末两者均 18 床，均 SOFA=10.0667、权重=2.0056，约束违反、求解失败与退回队列均为 0。本设定打平 |
| 六压力场景 | `python -m application.run_moo_phase4 --split eval --max-time 20` | 6 场景 × WS / Lex / ε，18 项均 OPTIMAL |
| payoff / ε / Pareto | `python -m application.run_moo_phase3 --split calib --levels 3 --max-time 15 --baseline-max-time 90` | 最终 27 网格、17 可行、3 非支配，HV=0.052130；WS / Lex 均 OPTIMAL。本次 balance payoff 范围退化为单一值，去重后网格小于 81 |
| 轨迹导出 | `python -m application.export_trajectory --steps 4` | 协议 2.0、4 transitions；另外断言状态连续、每步人数守恒、所有约束检查无违反 |

单测在本任务沙箱里使用仓库内的临时目录，例如 `--basetemp=reports/pytest-final`；普通开发环境可使用默认临时目录。测试有一条第三方 AnyIO pytest 插件弃用警告，不影响结果。没有运行会重写特征表的 ETL 测试。

## 仍需进一步改进

- **独立验证**：当前 PPO checkpoint 的原始训练患者清单未作为可核验契约交付，3 episode 采样评估不能直接宣称与训练数据互斥的独立留出验证。应冻结训练/校准/评价患者清单，并做多随机种子与多资源布局实验。
- **时间可用性**：GBDT 以构造优先级公式为监督信号，当前 H5 在同一数据上拟合与预测；`los_hours` 来自整次住院记录，在线调度时未必已知。后续需使用决策时刻可获得的特征与独立训练/评价，才可检验预测泛化。
- **真实纵向状态**：滚动当前使用初始 SOFA 与规则周转。需要真实时间顺序的入出转、病情与设备事件，评估等待时长、病情演化和约束标记准确性；现有 ISO/vent 需求仍为启发式。
- **offline RL**：当前 `train_ppo` 与仿真环境交互，不读取导出的摘要包。CQL/IQL、偏好条件策略与完整逐患者 observation/action/reward 仍需单独实现与验收。`hybrid` 是显式预留扩展。
- **实验边界**：本次小池和修复后的 H6 中多种方法打平。payoff 观测范围受单目标最优解的其他目标取值影响，不是完整 Pareto 空间的真实 nadir；本次 balance 轴退化，也说明网格覆盖仍需改进。旧报告中的 81/54/4/HV=0.038794 以及本次修复中间结果 81/51/4/HV=0.025479 均不代表最终代码输出，不能跨输入、阈值或归一化范围比较 HV 后宣称算法变好或变坏。

本文仅记录本次本地实现与验证，不将工程通过等同于临床效果或学术领先证明。
