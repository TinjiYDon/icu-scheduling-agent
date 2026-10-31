# H10 · 前沿适配 + 滚动 HV–churn

> 状态：**研究原型（合成演示）**。只依赖 numpy；不读数据库、不跑 CP-SAT/MIMIC、不访问网络。
> 代码：`domain/optimizer/pareto_io.py` · 脚本：`scripts/hv_churn_demo.py` · 测试：`tests/test_pareto_io.py`
> 关联：[PARETO_DECISION.md](PARETO_DECISION.md)（H10 决策层）· `moo_phase3`（前沿生成/HV）· H6 滚动 · P4 前沿质量。

## 1. 为什么需要“前沿适配”

`pareto_decision` 只吃 `(n, m)` 的数值矩阵，但仓库里前沿的落盘 schema 至少三种：

| 来源 | 形状 | 问题 |
|---|---|---|
| `moo_phase3.ObjectivePoint` / `as_dict()` | `{"values": {...}, "source": "s1", ...}` | 目标是**字典**，键序不定、含元数据 |
| 外部 JSON 报告 | `{"front": [{"f0": 0.8, "f1": 0.2}, ...]}` | 常量键名，缺 `source` |
| 手写/脚本内 | `list[list[float]]` | 无 id，行列可能不齐 |

不先统一，滚动指标（HV/周转/换床）就没法跨步比较。`pareto_io` 只做**解析 + 对齐 + 归一化**，
不重复前沿生成，也不替代 CP-SAT。

## 2. 三种输入 schema

```python
# 1) 裸矩阵：每行一个解，全部最大化
parse_front([[1.0, 0.0], [0.0, 1.0]])
# -> (array([[1.,0.],[0.,1.]]), ["sol_0", "sol_1"])

# 2) moo_phase3 ObjectivePoint 风格（也接受裸 list[as_dict()]）
parse_front({"points": [{"values": {"occupancy": 20, "wait": 5}, "source": "s1"}]})
# -> (array([[20., 5.]]), ["s1"])

# 3) 扁平常量键
parse_front({"front": [{"f0": 0.8, "f1": 0.2}]})
# -> (array([[0.8, 0.2]]), ["sol_0"])
```

规则：

- `objectives` 给定时**按其顺序**取列；否则取**所有行键的并集排序**（字母序）。
- ids 优先 `source` → `id` → `name`，否则 `sol_<index>`；长度必须与行数一致。
- 空输入、非二维输入、行/列不一致、缺目标键、非数值 → `ValueError`。
- `parse_front` **不做归一化**；归一化单独调用 `normalize_points`，避免“解析即改变数值”的隐式副作用。

## 3. 公式

全部目标**越大越好**，`f` 为归一化后的目标向量：

```
normalize:  f'_j = clip( (f_j − nadir_j) / (ideal_j − nadir_j), 0, 1 )
            ideal_j == nadir_j  ->  f'_j = 1.0
HV_t      = Λ( ∪_{x∈F_t} [ref, f'(x)] )        # ref 默认全 0
turnover_t= 1 − |F_{t−1} ∩ F_t| / |F_{t−1} ∪ F_t|        # 非支配集（按 id）
churn_t   = |{p : bed_{t−1}(p) ≠ bed_t(p)}| / |P_{t−1} ∩ P_t|   # 换床率
```

- `turnover` 衡量**前沿身份**的稳定性（集合层面）；
- `churn` 衡量**分配**的稳定性（患者层面），二者一起才说明“重解一次要付多少操作代价”；
- 首步 `turnover = churn = 0.0`（无前驱）。

## 4. API

```python
from domain.optimizer.pareto_io import (
    FrontSnapshot,        # step / ids / points(normalized) / raw
    parse_front,          # payload, objectives=None -> (points, ids)
    normalize_points,     # points, ideal=None, nadir=None -> ndarray
    hv_churn_series,      # fronts, assignments, ref=None -> list[dict]
    summarize_hv_churn,   # series -> dict
)
```

| 函数 | 输入 | 输出 |
|---|---|---|
| `parse_front` | 上述三种 payload | `(np.ndarray (n,m), list[str])`，未归一化 |
| `normalize_points` | 矩阵 + 可选 ideal/nadir | `np.ndarray` ∈ [0,1]，常量维 = 1.0 |
| `hv_churn_series` | `list[FrontSnapshot]` + `list[dict[patient, bed]]` | `[{"step","hv","n_front","turnover","churn"}]` |
| `summarize_hv_churn` | series | `{"n_steps","mean_hv","total_churn","mean_turnover","last_hv"}` |

约定：`fronts` 与 `assignments` 长度必须一致，否则 `ValueError`；`ref` 维数须与目标维数一致。
空 series → 汇总全 0（`n_steps=0`），便于下游直接画图/落表。

## 5. 运行与合成示例

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe scripts/hv_churn_demo.py --steps 5 --seed 0
```

输出（2026-10-31，20 个候选解池 / 每步 ±0.06 扰动 / 每步换 10% 床）：

| step | n_front | hv | turnover | churn |
|---:|---:|---:|---:|---:|
| 0 | 10 | 0.51799 | 0.0 | 0.0 |
| 1 | 13 | 0.336053 | 0.647059 | 0.1 |
| 2 | 9 | 0.450693 | 0.705882 | 0.1 |
| 3 | 12 | 0.430709 | 0.6 | 0.1 |
| 4 | 11 | 0.341402 | 0.647059 | 0.1 |

| summary | value |
|---|---:|
| n_steps | 5 |
| mean_hv | 0.415369 |
| total_churn | 0.4 |
| mean_turnover | 0.52 |
| last_hv | 0.341402 |

JSON 落在 `reports/pareto_decision/hv_churn_demo.json`（`config` / `series` / `summary` /
`note: synthetic only`），可被报告/Streamlit 直接读。

**读法**：合成前沿每步做**独立 min-max 归一化**，所以 HV 比的是“形状”而不是绝对水平；
HV 波动大 + turnover 高 = 候选池在扰动下非支配集频繁重排，说明真实场景下需要
“重解节流 / 稳定化”而不是每步全量重排。

## 6. 与既有模块的关系

| 模块 | 关系 |
|---|---|
| H10 `pareto_decision` | 复用 `hypervolume` / `front_turnover` / `assignment_churn`，不重写公式；本模块补**入口适配 + 跨步序列** |
| `moo_phase3` | `ObjectivePoint` 是 schema 2 的来源；HV 复用其精确实现 `_hv_exact` |
| H6 滚动 | `hv_churn_series` 就是滚动重解的稳定性打分器，可与 `reports/rolling_contrast.json` 的步序列对齐 |
| P4 前沿质量 | 前沿点太少时 HV 数值不稳（4 点前沿≈单点），应先用自适应 ε 扫描 + NSGA-II 对照 + 多 seed 提升再谈滚动指标 |
| H7 RFCC/CARE | **不依赖**；CARE 判别力未解决，不作为前沿质量依据 |

## 7. 局限

1. **合成数据**：demo 的前沿与分配均为合成，`turnover/ churn` 数值不构成 ICU 实证。
2. **归一化口径**：默认按**每一步自身**的 min-max，跨步 HV 只可比形状；若要绝对可比，须传入**全窗共用**的 `ideal/nadir`（固定参考点）。
3. **数据质量前置**：真实接入需先完成数据授权（F1）与数据质量修复，且 `reports/moo/*.json` 的目标口径要经 P4 校准。
4. **无临床结论**：本模块只度量“前沿/分配稳不稳”，不评价临床收益，也不替代 CP-SAT 的可行性约束。
