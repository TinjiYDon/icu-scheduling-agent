# S2-MOO：多目标求解方法对照

> 状态：阶段 1 ✅ · **阶段 2 ✅（2026-09-24）** · 下一拍阶段 3（ε 网格 / payoff）
>
> 范围：同一 ICU 候选池、床位资源和硬约束下，对比 Weighted Sum、Lexicographic 与 ε-Constraint。
>
> 非范围：本阶段不同时改造滚动事件流、动态 SOFA、PPO 或鲁棒优化。

## 研究问题

当前 CP-SAT 使用 λ 加权和，只给出一个由权重决定的折中解。S2-MOO 保持决策变量与硬约束不变，仅替换多目标决策机制，回答：

1. 加权和是否对权重与量纲敏感；
2. 词典序是否能稳定保证业务优先级；
3. ε-constraint 是否能得到更完整、可解释的 Pareto 候选集；
4. 三种方法在方案质量与求解时间上有何差异。

## 共同模型

### 硬约束

- 每张床至多一位患者；
- 每位患者至多一张床；
- 隔离需求必须进入隔离床；
- 呼吸机需求不得超过呼吸机容量。

硬约束不参与目标权衡。任何方法都不能通过违反硬约束换取更好的目标值。

### 阶段 2 共用目标（语义已校正）

| λ 键名 | 方向 | 表达式（canonical） | 说明 |
|---|---:|---|---|
| `occupancy` | max | 已分配患者数 (`beds_filled`) | 先保证可行床位得到使用 |
| `high_risk` | max | 已分配 SOFA≥10 数 (`high_risk_served`) | 显式临床优先 |
| `wait` | max | Σ priority_weight (`priority_served`) | **兼容旧键**；不是真实等待时长 |
| `overload` | min | SOFA≥10 且非隔离床的 SOFA 累加 (`high_risk_on_regular_beds`) | **acuity 错配**；低危占普通床不计 |
| `zone_mismatch` | min | 非偏好科室分配数 | 降低跨区安置 |
| `move` | min | 已在床患者换床数 | 滚动场景稳定性 |
| `balance` | min | 配置床区标准化利用率 max−min | 区大小不等时公平比较 |

披露字段：`result["objective_semantics"]` · `evaluation.priority_served` · `evaluation.high_risk_on_regular`。

## 三种求解策略

### Weighted Sum

保留现有 λ 与归一化系数，作为向后兼容基线：

```text
max  λ_occ·occupancy + λ_wait·wait
   + λ_risk·high_risk
   - λ_over·overload - λ_zone·zone_mismatch
   - λ_move·move - λ_bal·balance
```

### Lexicographic

默认层级：

```text
occupancy > high_risk > wait > overload > zone_mismatch > move > balance
```

逐层求解；每层得到可证明最优值后，将该值以等式锁定，再进入下一层。如果某一层仅得到 `FEASIBLE`，结果必须标记 `exact_hierarchy=false`，不得宣称得到严格词典序最优解。

### ε-Constraint

选择一个主目标，例如最大化 `wait`，其余目标变成方向感知的阈值约束：

```text
occupancy >= ε_occupancy
high_risk >= ε_high_risk
overload <= ε_overload
zone_mismatch <= ε_zone
move <= ε_move
balance <= ε_balance
```

阶段 3 先通过单目标 payoff table 获得各目标的理想值和取值范围，再生成 ε 网格；不凭经验随意指定 Pareto 扫描范围。

## 实施分期

| 阶段 | 内容 | 验收 |
|---|---|---|
| 1 ✅ | 统一目标规格；三种求解模式；阶段状态与累计时间 | 玩具模型单测 + 真实 MIMIC 只读求解 |
| 2 ✅ | 目标语义：`wait`→priority_served 披露；`overload`→高危落普通床；balance 区标准化 | `tests/test_objective_semantics.py`；旧 λ 键兼容 |
| 3 | payoff table、ε 网格、非支配解与 hypervolume | 可复现实验 CSV/JSON |
| 4 | 六场景对照与 calib/eval 报告 | 相同实例、相同时间预算、统一结果表 |
| 5 | Streamlit 展示与论文表格 | 方法、Pareto 与敏感性图可解释 |

## 实验场景

1. 正常容量；
2. 总床位不足；
3. 隔离床不足；
4. 呼吸机不足；
5. 高 SOFA 患者集中；
6. 科室需求不均衡。

每个场景固定患者集合、床位资源、随机种子、硬约束和总求解时间。报告原始目标值、分配率、高危等待、错区率、资源利用率、状态、累计时间与最优性信息。

## 代码接口

```python
run_assignment(objective_mode="weighted_sum")

run_assignment(
    objective_mode="lexicographic",
    objective_order=[
        "occupancy", "high_risk", "wait", "overload", "zone_mismatch", "move", "balance"
    ],
)

run_assignment(
    objective_mode="epsilon_constraint",
    epsilon_primary="wait",
    epsilon_bounds={
        "occupancy": 20,
        "high_risk": 8,
        "overload": 180,
        "zone_mismatch": 5,
        "move": 0,
        "balance": 2,
    },
)
```

## 阶段 1 验收记录

2026-09-23 在本地真实 Layer1 数据上以 `split="calib"`、`persist=False` 验证：

| 方法 | 状态 | 分配 | 高危分配 | priority served | 累计求解时间 |
|---|---|---:|---:|---:|---:|
| Weighted Sum | OPTIMAL | 20 | 17 | 41,800 | 0.68 s |
| Lexicographic | OPTIMAL（严格层级） | 20 | 17 | 41,900 | 5.47 s |
| ε-Constraint（单组阈值） | OPTIMAL | 20 | 17 | 41,900 | 0.69 s |

这些数值仅用于证明三种内核在同一真实候选池上可运行，不是最终方法优劣结论。最终结论必须来自阶段 3–4 的统一 ε 网格与多场景实验。

## 文献映射

- [多目标重调度综述](https://doi.org/10.3390/math12203176)：事前偏好、事后 Pareto 与方法分类；
- [Makboul et al.](https://doi.org/10.1016/j.ejor.2024.08.022)：四目标 ε-constraint、Pareto 与 hypervolume；
- [Fallahpour et al.](https://doi.org/10.1016/j.dajour.2024.100475)：医疗调度中增强 ε-constraint 与加权法对比；
- [化疗多预约](https://arxiv.org/abs/2309.07532)：顺序求解的词典序多目标；
- [院内转运](https://doi.org/10.1007/s00291-023-00741-z)：异量纲目标、严格/放宽词典序与实时求解。
