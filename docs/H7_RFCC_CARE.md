# H7 · 新机制 RFCC + 新指数 CARE/UHRM

> 2026-10-09 · **本仓具名创新点**（相对教科书 WS/Lex/ε）  
> 代码：`clinical_cascade` · `domain/optimizer/clinical_cascade.py` · `domain/ops/care_index.py`

## 为什么算「新」

| 旧（教科书/本仓已有） | 新（H7） |
|----------------------|----------|
| 加权和 · 占用优先词典序 · ε-约束 | **RFCC**：稀缺门控下的**风险优先临床级联** |
| 只用 assigned / wait 等原始目标 | **CARE / UHRM** 具名评价指数 |
| 机理不随「人是否多于床」切换 | **Scarcity gate** 自动切换序 |

不是新发明 CP-SAT 求解器，而是 **ICU 场景下的新决策机制 + 新评价指标**。

## 新机制：RFCC

**全称：** Scarcity-Triggered Risk-First Clinical Cascade  
**代码模式：** `objective_mode="clinical_cascade"`

- 若 \(n_{\mathrm{patients}} > n_{\mathrm{beds}}\)（稀缺）：  
  词典序 = **high_risk → overload(min) → wait → occupancy → …**  
  （先保高危覆盖与病情匹配，再谈填满床）
- 若床位充裕：  
  词典序 = **occupancy → high_risk → …**（经典填床优先）

标准占用优先 Lex **没有**这道稀缺门控，也不会在稀缺时把 overload 紧挨高危之后最小化。

## 新指数：CARE 与 UHRM

**UHRM**（Unserved High-Risk Mass）— 未分床高危患者的优先级质量之和：

\[
\mathrm{UHRM}=\sum_{i\in\mathcal{H},\,a_i=0} w_i
\]

**CARE**（Clinical Allocation Risk-Equity）：

\[
\mathrm{CARE}
=\underbrace{\frac{|\mathcal{H}\cap\mathrm{Assigned}|}{|\mathcal{H}|}}_{\mathrm{cover}}
-\alpha\cdot\underbrace{\frac{f_{\mathrm{ov}}}{10\cdot\max(|\mathcal{H}\cap\mathrm{Assigned}|,1)}}_{\mathrm{overload\_norm}}
-\beta\cdot\underbrace{\frac{\mathrm{UHRM}}{\sum_{i\in\mathcal{H}}w_i+\varepsilon}}_{\mathrm{uhrm\_norm}}
\]

默认 \(\alpha=\beta=0.35\)。CARE 越高越好：多收高危、少错配、少浪费高危优先级质量。

每次 `run_assignment` 的 `evaluation.care` / `care_index` 均写出。

## 怎么跑

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -c "from domain.optimizer.cp_sat import run_assignment; import json; print(json.dumps(run_assignment(persist=False, objective_mode='clinical_cascade', stay_ids=None), ensure_ascii=False)[:500])"
.\.venv\Scripts\python.exe -m application.run_method_bakeoff --candidate-patients 40
```

Bake-off 现含：greedy · WS · Lex · ε · **clinical_cascade**，并输出 CARE/UHRM。

## 答辩一句话

> 我们提出面向 ICU 的 **RFCC 稀缺触发风险优先级联**，并定义 **CARE/UHRM** 指数刻画「高危覆盖–错配–未服务质量」权衡；相对只调 λ 或占用优先 Lex，这是场景化的新机制与新指标。
