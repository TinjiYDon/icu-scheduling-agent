# H10 · Pareto 决策层：前沿价值与偏好稳健排序

> 状态：**研究原型（合成演示）**。不读数据库、不跑求解器；前沿由调用方注入。
> 代码：`domain/optimizer/pareto_decision.py` · 脚本：`scripts/pareto_decision_demo.py` · 测试：`tests/test_pareto_decision.py`
> 关联：`moo_phase3`（前沿生成/HV）、H4-S（WS/Lex/ε 对照）、H6（滚动）、H7（RFCC/CARE；**注意其判别力问题未解决**）。

## 1. 为什么需要“决策层”

仓库已经有非支配过滤 + 精确超体积（`moo_phase3`），但那只回答“哪些解互不支配”。医生最终只能选一个方案，缺的是：

- 这组前沿**比单一固定权重解多值多少钱**（VoF）；
- 选错的**期望/最坏后悔**多大（CoM）；
- 在偏好不确定时，**按最坏后悔怎么排序**（MMR）；
- 滚动重解后，前沿/分配**稳不稳**（turnover / churn）。

本模块只做这些决策层指标，**不重复**前沿生成，也不替代 CP-SAT。

## 2. 定义

约定：目标向量已归一化、全部**越大越好**。`c(x;w) = −w·f(x)`（越小越好），`w` 在单纯形上。

```
V*(w) = min_{x∈F} c(x;w)                 # 偏好 w 下的前沿最优
VoF   = E_w[ c(x_single;w) − V*(w) ]      # 前沿价值（完美偏好信息）
CoM   = max_w[ c(x_single;w) − V*(w) ]    # 误配代价（最坏偏好）
MMR(x) = max_w[ c(x;w) − V*(w) ]          # 解 x 的最坏后悔；升序即 MMR 排序
turnover = 1 − |F_t ∩ F_{t+1}| / |F_t ∪ F_{t+1}|
churn    = 换床人数 / 两期共同患者数
```

`VoF` 是“有前沿 + 知道偏好”相对“固定单解”的期望收益；`CoM` 是同一单解在最坏偏好下的后悔。二者一起看：VoF 大说明前沿有价值，CoM 大说明固定解风险高。

## 3. API

```python
from domain.optimizer.pareto_decision import (
    nondominated_indices, normalize_front, hypervolume,
    simplex_weights, value_of_front, minimax_regret_ranking,
    front_turnover, assignment_churn, summarize_front,
)
```

- `summarize_front(front, single, weights, ref)` → `FrontSummary`（HV / VoF / CoM / MMR top-5）；
- `value_of_front` 返回 `regret_matrix`（n×s），可用于画“偏好–后悔”热图；
- `normalize_front(values, ideal, nadir)` 把各目标映射到 [0,1]；
- 所有函数对输入做 shape 校验，不读全局状态。

## 4. 运行与合成示例

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe scripts/pareto_decision_demo.py --n 60 --objectives 2 --seed 0
```

输出（2026-10-31，合成 60 点前沿，1000 组 Dirichlet 偏好）：

| metric | value |
|---|---:|
| hypervolume | 0.483364 |
| VoF | 0.241821 |
| CoM | 0.539427 |
| front_turnover(example) | 0.032787 |
| assignment_churn(example) | 0.2 |

**这不是 ICU 实证**：前沿是合成、偏好是 Dirichlet 假设。仅用于验证实现与指标口径；MIMIC 实验须在数据授权（F1）明确后进行，且先修数据质量。

## 5. 与现有模块的关系

| 模块 | 关系 |
|---|---|
| `moo_phase3` | 提供 `dominates` / `filter_nondominated` / `_hv_exact`；本模块复用 HV，不重写 |
| H4-S（WS/Lex/ε） | 本模块输入的“前沿”可来自这些方法的解集；`single` 可来自 WS 固定 λ |
| H6 滚动 | 用 `front_turnover`/`assignment_churn` 量化重解稳定性；与 `rolling_contrast` 对接 |
| H7 RFCC/CARE | **不依赖**；CARE 在同池五法完全相同，尚未证明判别力，不能作为本模块的输入质量依据 |

## 6. 局限

1. **偏好未知**：合成用 Dirichlet；真实偏好需要医生问卷/选择实验，或做敏感性网格。
2. **未接求解器**：当前脚本用合成前沿；接 `reports/moo/summary_*.json` 需要一层适配（下一步）。
3. **单实例指标**：VoF/CoM 依赖前沿质量；前沿只有 4 个点时数值不稳定，应先做 P4（自适应 ε 扫描 + NSGA-II 对照 + 多 seed）。
4. **无临床声明**：VoF/MMR 是决策指标，不是临床效果。

## 7. 下一步

1. 适配 `reports/moo/summary_*.json` / `run_moo_phase3` 输出，跑 6 场景 × 5 seed 的 VoF/CoM。
2. 接 `rolling_contrast`：画 HV–churn 曲线，比较 naive / freeze / lookahead / 迟滞。
3. 偏好来源：三情景（效率/公平/安全）+ 医生问卷（若可得）。
4. 数据质量修复（隔离、priority、fixed_sample、los 单位）完成后，再做 MIMIC 实证；F1 未过不跑。
