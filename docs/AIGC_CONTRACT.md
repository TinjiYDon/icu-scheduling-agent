# AIGC · 语义可用性契约（DAC）

> 状态：**研究原型 / 合成演示**。只依赖 numpy；不读数据库、不跑 CP-SAT/MIMIC、不访问网络。
> 代码：`domain/optimizer/data_contract.py` · `fd_stress.py` · `pool_effect.py`
> 脚本：`scripts/aigc_contract_demo.py` · 测试：`tests/test_data_contract.py` / `test_fd_stress.py` / `test_pool_effect.py`
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

## 6. Demo 结果（合成，seed = 0，n = 200）

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

## 7. 局限

- **合成数据，不是临床证据**：`make_synthetic_columns` 只复现三条已知语义缺陷的形态，
  数字不能引用为 MIMIC 结果，也不构成床旁结论；
- 外部 LLM **只喂合成数据**，不把真实 stay 记录发给任何外部服务；
- `spurious_dof` 是**结构计数**，不判断权重是否合理（那是 `objective_semantics` 的事）；
- `ranking_stability` 对 2-D 目标矩阵按行求和降维，只是稳定性代理，不是多目标前沿比较
  （后者用 [PARETO_DECISION.md](PARETO_DECISION.md) 的 VoF/MMR/HV）；
- DAC 判定依赖 `fd_map` 与契约声明的**完整性**：漏声明的依赖不会被发现，这是“契约”而非“发现”工具。

## 8. 与 OptiTrust / OptiBench 的差异

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
