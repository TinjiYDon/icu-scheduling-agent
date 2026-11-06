# SOFA 时序与滚动 Pareto 实施记录

日期：2026-11-04。基础：main `d240006`；分支 `feat/sofa-time-rolling-pareto`。

## FACTS / 范围

- 原始需求：`origin/main-archive:MULTIOBJECTIVE_TASKS.md` D3、P8，及同分支 `MULTIOBJECTIVE_THEORY.md` 的 f5 定义。核对时 archive 提交为 `a6b9fbf`。archive 仅作需求依据，不整支合并。
- D3：旧评分只有肾/肝/凝血，hour_index=0；补六分量与时间标签。
- P8：每 2h 重解、上一轮床位映射、f5 与方案相似度、24h 验证。没有要求预测未来到达或新增优化目标。
- main 已有七目标、ε 网格、HV/churn；复用现有求解器。archive 的 previous_beds 对应 main 的 occupied_beds。
- 本地已有 MIMIC-IV 3.1 ZIP。只提取固定种子小样本；大表可能须顺序扫描，不做全量评分/优化。原始数据、患者级产物不入 Git。
- 用户已授权上述实现；结果分析由其他成员负责。本次不训练预测器、不改 UI、不重做大规模对照。

## 口径先行

- 决策步长 2h 与评分回顾窗 24h 分开。默认 ICU 24h 后开始回放，执行 24h；评分输出覆盖 0–48h，早期不完整窗口必须标记。
- 事件发生时间与记录可见时间均不得晚于决策时刻；保留缺失信息，不以未来观测补历史。
- SOFA 六分量可计算不代表每名患者六项均有观测；缺失分量按显式规则计入总分，并报告覆盖情况。
- MIMIC 患者日期不能直接拼成真实并发队列。回放使用患者相对临床时间与构造调度时钟，入出院仍为固定费率模拟，不宣称真实病区轨迹。
- f5 只计仍被分配的既有患者换床；新增/正常出院不计。住院患者保留规则、零共同患者的相似度和选择哪个 Pareto 方案均须写清。
- 完整 SOFA 后沿用 sofa_rule（1+s/10）作为明确基线，不借此引入新优先级模型；不宣称优先级与 SOFA 已独立。

## ACCEPTANCE

1. 六分量阈值、单位、缺失处理、回顾窗、未来信息排除有合成边界测试。
2. 固定样本/seed 可复跑，每步评分确实来自对应临床时点。
3. 24h（12×2h）回放，床位唯一、患者守恒、资源约束满足；每轮保存决策前映射及执行结果。
4. f5 可从映射独立重算；用构造案例验证非零换床，真实样本允许为零。
5. 同轮 ε 扫描使用相同候选与比较基准；可行点满足 ε，前沿无被支配点；保存七目标和求解状态。
6. 提供评分定义、滚动数学模型、复跑命令、限制和验证记录。

## 环境说明

AGENTS.md 要求的 complex-project-harness preflight 在本机不存在，preflight.yaml 也引用另一台机器的路径；不伪造通过。以本任务的依赖检查、定向测试与小样本 smoke 记录替代。仓库 S4 状态不自动变更；本任务为用户明确授权的 D3/P8 补齐。

## 实施与验证

实现文件：

- `domain/scoring/sofa_full.py`：六分量与可见时间过滤；`data_access/mimic_sample.py`：抽样与流式缓存。
- `scripts/prepare_sofa_sample.py`：原始 ZIP → 缓存 → 0–48h 评分 JSON。
- `domain/rolling/timed_pareto.py` / `application/run_timed_pareto.py`：当前评分 → 每步 reference / payoff / ε 备选 → 轨迹。
- `run_assignment(candidate_rows=..., persist=False)`：不读数据库；`solver_seed=0`：单线程固定种子；`retain_occupied=True`：住院连续性。
- 修正原有病区失配辅助变量：从不等式改为精确计数，避免未优化此项的锚点返回虚高值；ISO 与偏好病区的并集只计一次。

独立复核已修复 GCS 从 ETT 恢复时错误携带低反应项、PaO₂ 的 `mm Hg` 单位识别、回放资源容量和标签不一致、缓存续跑丢计数；补有回归测试。PaO₂ 单位修复通过已抽取 lab 的单位分布确认必要性。独立轨迹审计另发现并修复了 live occupied 字典与历史 assignments 共用引用的问题；下一轮出院不会再改写上一轮快照，回归测试逐步核对快照床位数与 occupancy 一致。

### 复跑命令（仓库根目录）

```powershell
# 首次：只筛选50例指定项目，不解压完整表；完成表会缓存。
.\.venv\Scripts\python.exe -u -m scripts.prepare_sofa_sample --zip ..\mimic-iv-3.1.zip --cache artifacts/sofa_sample --size 50 --seed 42 --min-stay-hours 48 --hours 48 --extract-only
# 后续改评分规则，只需重算小样本缓存。
.\.venv\Scripts\python.exe -m scripts.prepare_sofa_sample --score-only
# 24h、12次2h转移；初始状态另记，共13快照。
.\.venv\Scripts\python.exe -u -m application.run_timed_pareto --input artifacts/sofa_sample/sofa_sample.json --output reports/rolling/timed_pareto.json --sample-size 50 --beds 20 --steps 12 --seed 42 --levels 2 --max-time 3
```

抽样产物不写回已有数据库，历史三分量 dump 和 UI 结果不会被此次50例覆盖。完整评分契约见 [SOFA_SCORING.md](SOFA_SCORING.md)，滚动公式、执行方案规则和输出解释见 [ROLLING_PARETO_MODEL.md](ROLLING_PARETO_MODEL.md)。

### 验证记录（2026-11-04）

- Python 3.13.9、OR-Tools 9.15.6755、pandas 3.0.5、numpy 2.5.1。
- 103 项定向测试通过（包含新链路、真实 CP-SAT、小样本 ZIP 往返、原有多目标和 L4 接口回归）；新增/修改的 Python 文件通过 ruff。
- 已从真实 ZIP 选出50个 ICU stays，仅保留指定项目：lab 1090条、chart 5914条、input 227条、output 1199条；生成1250条（每例0,2,...,48h）评分。
- 入科24h的50例中，12例六个分量均有可评分输入。其余保留缺失mask；GCS正常补值、未知支持、尿量覆盖和长输注等质量规则仍须同时阅读，不能把“可评分”当作每个输入都完整实测。

| 分量 | 0–48h全部1250条快照中有可评分输入的条数 |
|---|---:|
| 呼吸 | 450 |
| 凝血 | 1037 |
| 肝 | 440 |
| 循环 | 1168 |
| 神经 | 1142 |
| 肾 | 1022 |

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_sofa_full.py tests/test_mimic_sample.py tests/test_timed_pareto.py tests/test_sofa_rolling_integration.py tests/test_assignment_rows.py tests/test_multiobjective.py tests/test_moo_phase3.py tests/test_objective_semantics.py tests/test_pareto_io.py tests/test_pareto_decision.py tests/test_plan.py tests/test_smoke.py tests/test_mcp_optimize.py tests/test_simulate_metrics.py tests/test_cp_sat_split.py -q --basetemp artifacts/pytest_sofa_rolling_check
```

### 24h 回放与复现审计：通过

- 固定 seed=42、50 stays、20床（4 ISO/8呼吸机资源模板）、warmup=24h、12次2h转移，共13快照。隔离/呼吸机需求启发式仅在此入口关闭，资源模板未被删除。
- 13次实际执行的 weighted reference 均 OPTIMAL；每次20床，患者状态守恒、住院患者保留、历史快照完整且独立。
- ε 网格因整数范围退化，合计92次：76 OPTIMAL、16 INFEASIBLE；无普通程序错误。每轮采样非支配点数依次为 `3,2,1,1,4,3,2,2,4,3,3,4,4`。这是扫描验收，不是完整前沿覆盖或效果分析。
- 执行方案本次 f5 均为0；可行 Pareto 备选中有非零 f5，且与各方案的床位映射独立重算一致。另有强制换床小例回归，未为制造非零结果修改真实轨迹。
- 两次完整回放的分床、目标值、评分引用、事件及前沿备选一致（不要求运行耗时相同）。语义内容 SHA-256：`d58ac31a90674ea923c02a414379b547391cbd0eb8a4b0ce6a8a5f5a16ed06fa`。
- 对1250条评分递归核对证据时间不晚于评分端点；逐步核对最新可用评分、床位唯一、患者分区守恒、f5、ε约束和采样非支配关系，全部通过。

本机输出（均不入 Git）：

| 文件 | 内容 |
|---|---|
| `artifacts/sofa_sample/manifest.json` | 原始压缩包身份、随机清单、扫描/保留计数 |
| `artifacts/sofa_sample/sofa_sample.json` | 1250条带时间标签的六分量评分与缺失/证据 |
| `reports/rolling/timed_pareto.json` | 每轮七目标、实际权重/尺度、完整分配和 ε 备选 |
| `reports/rolling/timed_pareto_repeat.json` | 独立重复回放 |
| `reports/rolling/acceptance.json` | 完整性与复现审计汇总 |

本次 D3/P8 小样本交付完成。剩余边界已写明：真实观测仍可能缺失、长stay选择偏差、合成队列、与官方回顾性 SQL 的时序差异、旧优先级共线、稀疏网格和跨步归一化限制。结果解释与更大规模研究由后续分析负责，不把此工程验收外推为临床结论。
