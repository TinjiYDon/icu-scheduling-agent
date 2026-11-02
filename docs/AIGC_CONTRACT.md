# AIGC · 语义可用性契约（DAC）

> 状态：**研究原型 / 合成演示**。只依赖 numpy；不读数据库、不跑 CP-SAT/MIMIC、不访问网络。
> 代码：`domain/optimizer/data_contract.py` · `fd_stress.py` · `pool_effect.py`
> 脚本：`scripts/aigc_contract_demo.py` · `scripts/aigc_mimic_grid.py`（MIMIC 网格运行器，见第 6 节）
> 测试：`tests/test_data_contract.py` / `test_fd_stress.py` / `test_pool_effect.py` / `test_aigc_grid.py`
> 关联：[MASTER_NARRATIVE.md](MASTER_NARRATIVE.md)（可审计）· [HV_CHURN.md](HV_CHURN.md)（滚动口径）· [PARETO_DECISION.md](PARETO_DECISION.md)

## 1. 为什么需要这份契约

把优化模型交给 LLM 生成（AIGC）之前，先要回答一个问题：**喂给它的字段，语义上到底能不能用？**
本仓三条实证发现正是反例，也都是硬资产：

| 发现 | 数字 | 语义后果 |
|---|---|---|
| 隔离启发式命中 | 76,157 / 94,458，top-20 中 19/20 需 ISO | `isolation` 不存在，只能由 `careunit` 关键词推 → **启发式字段**，不可当原始观测 |
| `priority ≡ 1 + sofa_total/10` | corr = 1.0，仅 13 个取值 | 所谓“优先级模型”是 SOFA 的线性重编码 → 两者同场即**伪自由度** |
| `los_hours` 实为“天” | 单位错 24× | LOS 窗口被放大，所有时间约束失真 → **unit_error** |

不做这层契约，AIGC 生成的模型会“语法正确、语义错误”：约束写得很漂亮，但用的字段是重编码的、
单位错的、或者根本只是启发式代理。DAC（Data Availability Contract）把这层判断变成
**可声明、可校验、可拒答**的纯函数。

## 2. DAC：可用性级别与判定

级别固定为六档（`AVAILABILITY_LEVELS`）：

| 级别 | 含义 | 处理 |
|---|---|---|
| `exact` | 原始观测，可直接当输入 | 通过 |
| `proxy` | 代理指标，与目标有已知偏移 | 通过，但需标注 |
| `heuristic` | 由关键词/规则推出（例如 isolation） | 通过，但需标注 |
| `stale` | 有，但时间窗已过期 | 违规 → 降级 |
| `unit_error` | 有，但单位/口径错（los_hours） | 违规 → 降级 |
| `missing` | 不存在 | 违规 → 拒绝 |

判定规则（`check_contract`）：

1. 字段可用级别 ∈ `{stale, unit_error, missing}` → 违规；`missing` 直接致命；
2. 冗余字段与其源字段/X 同时出现在列里 → 违规（除非在 `depends_on` 里已声明该依赖）；
3. 任一约束的字段不在列里 → 致命（`refuse`）；
4. 只有冗余 / 陈旧 → `degrade`；无违规 → `pass`。

`degrade_or_refuse(report, policy)` 把严重性映射成执行动作：

| policy | 行为 |
|---|---|
| `strict`（默认） | 任何违规 → `refuse`（AIGC 生成前的保守档） |
| `advisory` | 沿用报告自身 `action`（`degrade` 可跑但必须标注） |
| `lenient` | 违规最多 `degrade`，只有零违规才 `pass` |

## 3. FD 压测：伪自由度与对齐度

`KNOWN_FDS` 固化三条已知函数依赖：

```python
"priority_weight": ("1 + sofa_total / 10", ("sofa_total",))
"los_hours":       ("outtime - intime in days, mislabeled as hours", ())
"isolation":       ("careunit keyword heuristic", ("first_careunit",))
```

| 度量 | 定义 | 用途 |
|---|---|---|
| `spurious_dof(model_spec, fds)` | 变量同时引用冗余字段+依赖字段（无剔除说明）计 1；约束把冗余字段当独立输入计 1 | 模型的“假自由度”计数 |
| `field_alignment(model_spec, contracts)` | 模型引用字段中被契约声明且级别可用的比例 ∈ [0,1] | 模型是否跑在“已声明可用”的字段上 |
| `refusal_accuracy(reports, ground_truth)` | 契约“该拒的是否拒了”的准确率 ∈ [0,1] | 契约本身的判别力 |
| `ranking_stability(points_a, points_b, k=3)` | 两个排序 top-k 交集比例 ∈ [0,1] | 换了输入（或重编码）后排序是否还稳 |

`spurious_dof` 的“剔除说明”指 `excluded` / `derived` / `drop` 等键，或非空 `redundancy_note`——
即**审计过并显式声明**，不是真的把字段删掉。

## 4. 同池反事实（pool effect）

方法对照里最常见的口径污染是“两组方法跑在不同池子上”（不同 stay 子集、不同入出转调度、
不同资源上限）。同池反事实要求两组方法在同一批 stay 上重跑：

```
delta_naive  = metric_b^naive   − metric_a^naive
delta_match  = metric_b^matched − metric_a^matched
pool_effect  = delta_naive − delta_match
```

`decompose(delta_naive, delta_match, pool_gap_before?, pool_gap_after?)` 给出恒等式：

```
pool_effect + mechanism_effect + interaction = delta_naive
mechanism_effect = delta_match
pool_effect      = pool_gap_after − pool_gap_before   （未给池差时 = delta_naive − delta_match）
interaction      = 残差（未给池差时恒为 0）
```

给出池差时 `interaction ≠ 0` 说明两个比较**并非真的同池**（非线性指标、样本滑移、两套池子不同源）。

`summarize_pool_effect(results)` 汇总 `n_metrics / mean_pool_effect / mean_abs_pool_effect /
max_abs_pool_effect / max_abs_metric / positive_share / dominant_sign`。

## 5. API

```python
from domain.optimizer.data_contract import (
    AVAILABILITY_LEVELS,          # ("exact","proxy","heuristic","stale","unit_error","missing")
    FieldContract,                # name / availability / depends_on / redundant_with
    ConstraintContract,           # name / fields / failure_mode
    ContractReport,               # ok / violations / action ∈ {pass,degrade,refuse}
    check_contract,               # contracts, columns, fd_map -> ContractReport（纯函数）
    degrade_or_refuse,            # report, policy="strict" -> {"action","reason"}
    contract_from_dicts,          # [{name,fields,failure_mode}] -> tuple[ConstraintContract]
)

from domain.optimizer.fd_stress import (
    KNOWN_FDS, make_synthetic_columns(n, seed),
    spurious_dof, field_alignment, refusal_accuracy, ranking_stability,
)

from domain.optimizer.pool_effect import (
    pool_effect,                  # naive_a, naive_b, matched_a, matched_b -> dict
    decompose,                    # delta_naive, delta_match -> {pool,mechanism,interaction}
    summarize_pool_effect,        # results -> dict
)
```

约定：`check_contract` 纯函数、无 IO；`columns` 可传列名序列或 `{name: series}` 映射；
空输入、非数字、非法级别一律 `ValueError`，不做静默兜底。

## 6. MIMIC 网格运行器

`scripts/aigc_mimic_grid.py`：**6 场景 × N seed 的 ε 网格**，每个场景每 seed 记录
`n_feasible / n_front / hv / assigned / care / solve_time_sum`，再把场景两两喂给
`pool_effect` 得到 B_pool 表。它只**编排**，求解链仍是
`moo_phase3.run_payoff_table → run_epsilon_grid_scan → hypervolume`
（与 `application/run_moo_phase3.py` 同一条链），`solve` 回调换成
“固定候选池 + 场景 `resource_overrides`”的 `run_assignment`。

### 6.1 命令

```powershell
# 自检（合成池，30 候选 / 1 seed / levels 2 / max-time 2）——不读 MIMIC、不连库
.\.venv\Scripts\python.exe scripts/aigc_mimic_grid.py --smoke

# 合成池干跑（不读 MIMIC，可任意规模）
.\.venv\Scripts\python.exe scripts/aigc_mimic_grid.py --source synthetic --levels 2 --seeds 1

# 真实 MIMIC 网格（需 F1 确认 + 显式 AIGC_MIMIC_ALLOW=1）
$env:AIGC_MIMIC_ALLOW = "1"
.\.venv\Scripts\python.exe scripts/aigc_mimic_grid.py --levels 3 --seeds 5 --max-time 30
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `--scenarios` | `all`（6 个） | 逗号分隔场景 id |
| `--seeds` | `5` | seed 个数（0..N-1） |
| `--levels` | `3` | ε 网格水平数（≥2） |
| `--max-time` | `30` | 单次求解墙钟秒 |
| `--max-patients` | `200` | 候选池上限（`small_pool` 固定 50） |
| `--max-points` | 无 | 可选：每场景每 seed 的 ε 求解数上限（debug） |
| `--source` | `db` | `db`（MIMIC）或 `synthetic`（仓内合成池） |
| `--out` | `reports/aigc/mimic_grid.json` | 输出 JSON |
| `--smoke` | 关 | 覆盖为合成池 30 候选 / 1 seed / `levels 2` / `max-time 2` / 仅 `baseline` |

### 6.2 六个场景

| id | 覆盖 | 语义 |
|---|---|---|
| `baseline` | 无 | 默认 20 床 / 4 隔离 / 8 呼吸机 |
| `more_beds` | `n_beds=24` | 扩容（分区按比例缩放） |
| `fewer_vents` | `n_ventilators=4` | 呼吸机不足 |
| `more_iso` | `n_isolation_beds=8` | 隔离床扩容 |
| `small_pool` | 候选截断 50 | **只换池**，机制不变 |
| `high_acuity` | `priority_overrides` | SOFA≥10 的 `priority_weight` ×1.5 |

### 6.3 F1 门（DUA/CITI）

每次运行都打印 `F1-GATE: 需要 DUA/CITI 已确认`。数据合规上只有两种放行口径：

1. `--smoke` / `--source synthetic`：跑的是合成池，**不读 MIMIC**，直接放行；
2. `--source db` 且候选数 > 100：必须 `AIGC_MIMIC_ALLOW=1`，否则以非零码退出（`status: blocked`），
   防止误跑全量网格。

`--smoke` 的合成池注入方式：把 `domain.optimizer.cp_sat.get_engine` 换成内存假引擎（只换数据源，
不改 SQL/约束/目标语义），因此自检覆盖的是**真求解链**，`num_search_workers=1` + 固定
`random_seed` 保证可复现。合成池沿用 `priority = 1 + sofa_total/10` 的重编码关系，
**不能作为 MIMIC 证据引用**。

### 6.4 输出 schema

```json
{
  "config": {"smoke": false, "source": "db", "scenarios": ["..."], "seeds": [0,1,2,3,4],
             "levels": 3, "max_time_seconds": 30, "max_patients": 200,
             "gate": "AIGC_MIMIC_ALLOW=1", "seed_effect": "..."},
  "runs": [{"scenario": "baseline", "seed": 0, "n_feasible": 32, "n_front": 7,
            "hv": 0.0, "assigned": 20.0, "care": 5.0, "solve_time_sum": 0.0,
            "n_grid": 81, "pool_size": 200, "pool_cap": 200}],
  "scenarios": {"baseline": {"n_seeds": 5, "hv_mean": 0.0, "hv_std": 0.0,
                            "care_mean": 0.0, "assigned_mean": 0.0, ...}},
  "pool_effect": {"baseline": "baseline", "baseline_hv_mean": 0.0,
                  "rows": [{"scenario": "small_pool", "matched_pool_cap": 50,
                            "metrics": {"hv": {...}, "care": {...}}, "B_pool_hv": 0.0}],
                  "summary": {"n_metrics": 5, "mean_pool_effect": 0.0, ...}}
}
```

口径必须说明（写进报告时照抄）：

- `hv`：7 目标前沿在 payoff ideal/nadir 归一化后的超体积（`moo_phase3` 同一实现）；
- `assigned` / `care`：**非支配前沿上的均值**（`occupancy` → 已分床数、`high_risk` → SOFA≥10 覆盖数），
  前沿为空记 0；
- `hv_std`：**总体标准差**（`ddof=0`），1 个 seed 时为 0；
- **seed 的作用**：`synthetic` 源下 seed 决定合成池；`db` 源下池同源，seed 只影响 CP-SAT
  `random_seed`，因此 `hv_std` 反映求解器抖动而不是人群差异 —— 不要把它读成置信区间；
- **B_pool**：`naive_*` 是各场景跑在自己的池上，`matched_*` 是 baseline 重跑在**该场景的池**上，
  `pool_effect = delta_naive − delta_match`。所以 `small_pool` 的差值全部落进 `pool_effect`
  （纯池效应），`more_beds` / `fewer_vents` / `more_iso` / `high_acuity` 的 `pool_effect` 为 0
  （同池只换机制）。这是**口径自检**，不是“没有池效应”。

### 6.5 hermes 使用说明

1. 等 F1（DUA/CITI）确认后，`export AIGC_MIMIC_ALLOW=1`；
2. 先 `--levels 2 --seeds 1` 小网格验证环境（`--max-points` 可再缩）；
3. 再跑全量 `--levels 3 --seeds 5 --max-time 30 --out reports/aigc/mimic_grid.json`；
4. 交付只看 `config.gate`、`runs` 条数（= 场景数 × seed 数 + matched baseline）与
   `pool_effect.summary`；`status: blocked` 或非零码一律按阻塞上报，不要静默重试。

## 7. Demo 结果（合成，seed = 0，n = 200）

```powershell
.\.venv\Scripts\python.exe scripts/aigc_contract_demo.py --seed 0
# -> reports/aigc/contract_demo.json
```

| scenario | strict | advisory | violations | 说明 |
|---|---|---|---|---|
| raw | refuse | refuse | 3 | 缺 `n_isolation_beds`；`los_hours` 单位错；isolation 与 careunit 冗余 |
| degraded | refuse | degrade | 2 | 去掉容量约束后只剩冗余+单位错 |
| repaired | pass | pass | 0 | `los_days` 单位正确、隔离床数列补齐、冗余列剔除 |

`refusal_accuracy = 1.000`（raw 应拒，degraded/repaired 不应）。

| model_spec | spurious_DoF | alignment(vs raw) | alignment(vs repaired) |
|---|---:|---:|---:|
| naive | 3 | 0.667 | 0.500 |
| fd_audited | 0 | 1.000 | 0.500 |
| contract_aware | 0 | 0.667 | 1.000 |

即：**只看 `spurious_DoF` 会把 fd_audited 和 contract_aware 判成同级**，只有同时看“对齐度对哪套契约”
才能区分“解决了冗余”和“真正只用可用字段”。

`ranking_stability(k=3)`：sofa vs priority = **1.000**（重编码不改序）；sofa vs isolation = **0.000**
（启发式字段排序与病情无关）。

同池反事实：合成示例 `B_pool = 0.130`（整池口径高估机制增益 0.13）；
把 `reports/pto_decision_ablation.json`（H5/H7，`high_risk_waiting`）与
`reports/rolling_contrast.json`（H6，`mean_avg_sofa`）喂进去，`pool_effect = 0`——
说明现有对照都是**共享池**，池效应没有被分离出来。这正好是口径自检，而不是“没有池效应”。

## 8. 局限

- **合成数据，不是临床证据**：`make_synthetic_columns` 只复现三条已知语义缺陷的形态，
  数字不能引用为 MIMIC 结果，也不构成床旁结论；
- 外部 LLM **只喂合成数据**，不把真实 stay 记录发给任何外部服务；
- `spurious_dof` 是**结构计数**，不判断权重是否合理（那是 `objective_semantics` 的事）；
- `ranking_stability` 对 2-D 目标矩阵按行求和降维，只是稳定性代理，不是多目标前沿比较
  （后者用 [PARETO_DECISION.md](PARETO_DECISION.md) 的 VoF/MMR/HV）；
- DAC 判定依赖 `fd_map` 与契约声明的**完整性**：漏声明的依赖不会被发现，这是“契约”而非“发现”工具。

## 9. 与 OptiTrust / OptiBench 的差异

| 维度 | OptiTrust / OptiBench | 本仓 DAC |
|---|---|---|
| 关注点 | LLM 生成代码的**信任度 / 可执行正确性**；基准任务上的通过率 | 生成**优化模型前**的字段语义可用性，以及生成后的伪自由度/对齐度 |
| 判定输入 | 代码 + 测试用例 / 求解结果 | 字段契约（可用级别 + 依赖）+ 列清单 + model_spec |
| 失败处理 | 重试 / 拒绝生成 / 代码修复 | 三档显式动作：`pass` / `degrade`（标注后运行）/ `refuse` |
| 冗余处理 | 一般不建模 | 显式 `KNOWN_FDS` + `spurious_dof` 计数（priority ≡ 1+SOFA/10 这类重编码） |
| 口径污染 | 不在范围 | `pool_effect` 差值 + `decompose` 恒等式，把“换池子”和“换机制”拆开 |
| 证据级别 | benchmark 分数 | 合成演示 + 仓内报告自检，**不宣称 SOTA** |

一句话：OptiTrust/OptiBench 审的是“**代码对不对**”，DAC 审的是“**输入能不能用、用了多少真自由度**”，
两者互补，不能互相替代。
