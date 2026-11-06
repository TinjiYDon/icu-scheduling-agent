# 带时间标签的 SOFA 与滚动 Pareto：实现和数学口径

本次仅完成 `main-archive` 中 `MULTIOBJECTIVE_TASKS.md` 的 D3 数据接口与 P8 滚动接入：用已生成的六分量 SOFA、相对时间标签和上一轮床位状态，进行小样本重优化并记录 Pareto 备选方案。不新增目标、预测器、未来规划期或结果分析。代码入口为 `domain/rolling/timed_pareto.py`；旧的 `domain/rolling/engine.py` 保留兼容。

## 1. 文档与版本对应

- archive 中最后一个目标是挪床人数 $f_5$，不是新增“时间目标”。archive 使用 `previous_beds`；当前 main 对应参数为 `occupied_beds`。
- archive 的六目标在当前 main 中另有 `high_risk`，共七项目标。此次直接沿用当前 `moo_phase3.DEFAULT_OBJECTIVES` 的名称、方向和求值，不删除或重定义既有目标。
- 当前已有 payoff、ε 网格、非支配过滤和 HV 工具。此次复用 `run_payoff_table`、`run_epsilon_grid_scan`、`filter_nondominated`，不另造搜索算法。
- 旧引擎随机出入院并且仅读 `hour_index=0`；新入口显式读取逐时 SOFA，独立于数据库。数学定义以下文为准。

## 2. 两种时间窗口

**评分回顾窗**由上游评分流程定义。每条 SOFA 的 `hour_index=h` 是 ICU 入科后第 $h$ 小时的评分可用端点，`window_start/window_end` 记录其回顾范围；评分只能使用该端点以前允许读取的观测。评分规则、六分量映射、缺失和数据质量另见 `SOFA_SCORING.md`（由评分流程同步维护）。

**决策步长**固定为 $\Delta=2$ 小时。默认有初始决策 $t=0$ 和 12 次转移，模拟时钟 $\tau_t=2t$，共 24h、13 个状态快照。这是每步观察当前状态再优化的滚动重解；没有未来预测或多步联立规划，不能称为 lookahead。

默认 warmup 为 $h_0=24$。患者 $i$ 在合成队列中首次进入的时钟为 $a_i$，其可读取的临床相对年龄是：

$$h_i(t)=h_0+\tau_t-a_i.$$

初始患者 $a_i=0$；后来进入队列的患者从自己已经积累 24h 的资料开始回放。不同患者的原始日历日期**不对齐**：MIMIC 的患者日期偏移不能支持真实医院并发队列复原。这里的“到达”是进入合成调度候选队列，不宣称真实 ICU 入科时刻，也不宣称完成真实入院前分诊验证。

选择最新但不晚于当前年龄的评分：

$$h_i^*(t)=\max\{h\mid h\le h_i(t),\ (i,h)\text{ 有评分}\},\quad s_i(t)=s_{i,h_i^*(t)}.$$

不向前寻找未来评分，不用未来实际 LOS 排序或预测出院。没有可用评分、或 warmup 最新评分六分量全缺失的 stay，抽样前排除并输出 ID。某个后续端点六分量全缺失则明确停止，避免将其作为健康患者继续调度。部分分量缺失沿用上游明确披露的总分规则，并逐轮保留 `components`、`missing_components` 和 `quality_flags`；零分不代表六项都实测正常。

若后续没有新评分，则沿用最后可用值，并记录 `score_age_hours=h_i(t)-h_i^*(t)`。特别是较短住院结束后的回放，这属于陈旧观测的工程延续，不能据此解释真实病情。验证样本优先从有完整回放长度的较长 stays 抽取；这是验证样本的选择偏差，不能对完整患者群体外推。`outtime` 和未来实际 LOS 不进入求解器。

## 3. 合成队列与患者守恒

用单独的 `random.Random(seed)` 固定抽样顺序和事件，默认 `seed=42`。最多抽取50个符合 warmup 条件的患者，20床；初始候选数为 `min(sample,2*beds)`，其余尚未到达。候选 ID 固定排序，不依赖 set 或 SQL 返回顺序。

状态分成四个互斥集合：尚未到达 $P_t$、等候 $W_t$、住院 $O_t$、已出院 $D_t$。在任何完成的步骤必须满足：

$$P_t\mathbin{\dot\cup} W_t\mathbin{\dot\cup}O_t\mathbin{\dot\cup}D_t=I_{sample}.$$

每个非初始步骤先发生出院，再让新患者到达，最后求解。出院量在费率 $r_d>0$ 时为

$$d_t=\min\bigl(|O_{t-1}|,\max(1,\lfloor r_d|O_{t-1}|\rfloor)\bigr),$$

从当前住院 ID 中按固定随机数源抽取；$r_d=0$ 时为0。到达量在 $r_a>0$ 时为

$$a_t=\min\bigl(|P_{t-1}|,\max(1,\lfloor r_aB\rfloor)\bigr),$$

从固定抽样队列前端取人；$r_a=0$ 时为0。默认两个费率均为0.05。这是现有固定费率仿真的显式化，低费率时 `max(1,...)` 只是构造规则，不是从真实小时风险率估计的统计模型。

求解候选集为出院后仍住院者与当前等待者之并集。新到达者只进入等待，不先贪心分床，因此首次收治不误计为挪床。求解后，未分配候选者完整回到等候集；所有状态集合与样本核对，患者不会无声丢失。

默认 `retain_occupied=True`，要求未出院的原住院患者仍获一床：

$$\sum_b x_{ibt}=1,\quad i\in O_t^-.$$

其中 $O_t^-$ 是本次出院后、重优化前住院集。这是住院连续性的显式配置：不能通过将住院者踢出队列规避换床代价。`retain_occupied=False` 仅作为明确启用的研究配置，允许被挤出者回等待；输出 `displaced_to_waiting`，仍验证守恒。

## 4. 上一轮床位与最后一个目标

每轮固定 `predecision_beds={stay_id:bed_id}`，其含义是出院事件完成后、当前优化开始前的床位状态。记该床位为 $o_{it}$。本轮所有 reference、payoff、ε 组合使用完全相同的候选行、SOFA、资源、`predecision_beds` 和求解器种子；不能把某个备选方案执行后的床位反过来当本轮基准。

最后目标保持原义：

$$f_{5,t}(x)=\sum_{i\in O_t^-}\sum_{b\ne o_{it}}x_{ibt},\quad\min.$$

首次到达、首次收治和已经出院者都不计入换床。研究配置允许未收治时，该人的 $f_5$ 贡献也为0，所以必须同时记录被移除人数；默认住院连续性约束避免了这个规避途径。每一个返回的可行方案都保留完整分配明细，并将计算出的换床人数与 solver 的 `move` 对照。

令 $C_t=\mathrm{dom}(predecision_t)\cap\mathrm{dom}(assignments_t)$，则

$$churn_t=\frac{|\{i\in C_t:o_{it}\ne b_{it}\}|}{|C_t|},\quad similarity_t=1-churn_t.$$

当 $|C_t|=0$，按工程约定 churn=0、similarity=1，同时输出分母0，不能解释成“有住院患者且完全稳定”。初始步 $f_5=0$；新入院和出院不进入此换床率分母。

## 5. Pareto 扫描与实际执行规则

七项目标沿用 main。此入口采用明确的旧优先级基线

$$w_i(t)=1+s_i(t)/10.$$

这一权重与 SOFA 共线，使用它仅为了不引入新的拟合模型或未经说明的 LOS 代理；不宣称解决了 archive D2 的共线性问题，也不继承已在旧0–12分输入上训练的 GBDT 输出。既有高危阈值和重症错配定义保持 main 口径，需要分析者结合新0–24分输入解释。

每轮先运行当前既有加权和 reference，再用七次单目标求解构造 payoff 表。$f_0^I$ 为 payoff 中占用的最好值；设置占用下限

$$f_0\ge\lfloor\rho f_0^I\rfloor,\quad\rho=0.9.$$

然后使用现有 `wait` 为 ε 主目标，扫描 `overload`、`zone_mismatch`、`move`，默认每轴 `levels=2`，至多8次求解（范围退化时更少）。占用下限只加入这些 ε 求解；reference 沿用当前加权和，单独记录 `reference_meets_occupancy_floor`。每个扫描解的原始七维值、ε 参数、可行状态、分配明细均保留；非支配过滤在**当前扫描得到的可行集合**上执行。

实际执行的方案始终是既有 `weighted_sum` reference，不暗加新的偏好规则，也不声称 reference 必在扫描前沿上。输出 `reference_on_sampled_front`（目标向量是否与某个扫描非支配点相同）。若扫描未获得可行方案，输出空前沿和各次状态，reference 仍可执行；不能把空前沿说成数学上不存在可行解。

payoff 理想点/最差点是有限次锚点结果的逐列估计，不是严格全局 nadir 界。现有 helper 计算的 HV 使用每轮自身估计范围，仅为留存兼容字段；不同轮范围和候选集会变化，不能据此宣称跨步 HV 改善。`levels=2` 是接线验证用稀疏网格，不保证覆盖完整 Pareto 集。

默认关闭缺乏真实标签支撑的隔离和呼吸机硬约束（只对本入口设置，不改全局配置），使用既有 `scale_bed_layout` 资源覆盖：20床保持4张隔离床、8台呼吸机和原5病区布局，其他床数按已有工具缩放；禁用需求硬约束不改变普通床/隔离床集合，避免重定义 $f_2$。配置中保留完整资源。仍保留既有病区偏好/软惩罚。单线程 `solver_seed=0`；若达到时限只能报告 FEASIBLE，不提升为已证明最优。

## 6. 输入、输出与复跑

输入 JSON 包含 `stays` 和 `scores`；`stays` 至少有 `stay_id` 和可选 `first_careunit`；每条 score 至少包含 `stay_id`、`hour_index`、`sofa_total`、六项 `components`、`missing_components`，其余评分审计字段由上游保留。评分端点按 stay 唯一，负时间或不在0–24内的总分直接拒绝。默认应提供0–48h评分，24h warmup 后回放24h。

```powershell
.\.venv\Scripts\python.exe -m application.run_timed_pareto --input artifacts/sofa_sample/sofa_sample.json --output reports/rolling/timed_pareto.json --sample-size 50 --beds 20 --steps 12 --seed 42 --levels 2 --max-time 3
.\.venv\Scripts\python.exe -m pytest tests/test_timed_pareto.py -q
```

输出包括抽样/排除名单、配置、13步 history。每步记录评分端点及陈旧时长、七维目标、完整 `predecision_beds` 和 `assignments`、共同患者数、换床数/率、相似度、事件及四类状态、payoff/扫描/非支配方案和患者守恒结果。不读取或写入数据库，不修改源压缩包，不运行全量数据、不做效果结论。

`input_config` 保存评分抽样和时间窗配置；每步 `reference_details` 保存实际合并后的 λ（包含代码默认值）、目标归一化上界与整数系数、求解阶段及约束披露。后续数学模型应引用这些实际快照，而不能仅依赖可能已被修改的 YAML。ε 求解的 INFEASIBLE / UNKNOWN 与程序异常区分记录；不可行阈值不当作可行前沿点。

## 7. 验收与边界

无数据库小实例覆盖：必然换床时 $f_5$ 与前后床位比较一致；同一步各求解使用同一基准；未来评分改变不影响早期决策；全缺失首评分不会变成正常零分患者；研究配置的被挤出者返回等待；默认住院连续性；固定seed可复现的出入事件；24h过程患者守恒；非法步数/费率失败。

小样本自然出现所有步骤 $f_5=0$ 是合法结果，不为满足 archive “不再恒0”的字面要求制造换床。使用构造的必换床测试证明惩罚接入即可。队友后续分析须同时说明抽样、缺失、模拟到达/出院、陈旧评分、稀疏网格和旧优先级基线这些限制。
