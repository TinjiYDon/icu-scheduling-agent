# 架构 · 创新 · 数学算法 · 关键参数全览

> 展示用 SSOT · 2026-10-09  
> 配置真值来自 `configs/optimizer.yaml` · 公式与代码一致  
> 报告口播：[REPORT_SPEECH_COMPLETE.md](REPORT_SPEECH_COMPLETE.md) · H7：[H7_RFCC_CARE.md](H7_RFCC_CARE.md)

---

## 1. 系统架构（分层 + 数据流）

```text
┌─────────────────────────────────────────────────────────────┐
│  presentation/     Streamlit Ops 台 · MCP optimize_beds      │
└────────────────────────────┬────────────────────────────────┘
                             │ L4
┌────────────────────────────▼────────────────────────────────┐
│  application/      plan · simulate · moo_ui · h3_ui           │
│                    run_method_bakeoff · run_pto_ablation      │
│                    run_rolling_contrast · clinical_cascade    │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│  domain/                                                     │
│   scoring/     SOFA · GBDT priority (仓内，禁 decision)        │
│   optimizer/   CP-SAT · multiobjective · RFCC · CARE         │
│   rolling/     滚动再优化引擎                                 │
│   rl/          MaskablePPO 对照（默认不启用）                  │
│   ops/         Fair 对照 · bake-off · care_index              │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│  data_access/ + infra/     SQL · dump restore · configs       │
│  Layer1 MIMIC stays/SOFA ≈ 94458                              │
└─────────────────────────────────────────────────────────────┘
```

**默认策略：** `policy.default = cp_sat`（可审计）。PPO 仅研究对照轨。

---

## 2. 架构环 ↔ 创新点映射

| 架构环 | 做什么 | 对应创新 / 假设 | 入口 |
|--------|--------|-----------------|------|
| 数据 Layer1 | MIMIC stays + SOFA | 可复现底座 | dump / restore |
| 紧迫度 | SOFA / 公式 / GBDT → \(w_i\) | **H5** 决策质量 Jaccard | `run_pto_ablation` |
| 硬约束分床 | \(x_{ib}\) CP-SAT | H1 规则披露 | `cp_sat.py` |
| 多目标 | WS / Lex / ε | **H4** 机理对照 | 多目标页 |
| **RFCC** | 稀缺门控风险优先级联 | **H7 新机制** | `clinical_cascade` |
| **CARE/UHRM** | 评价指数 | **H7 新指数** | `care_index.py` |
| 滚动 | 再优化 vs 贪心填床 | **H6** | `run_rolling_contrast` |
| Fair 评测 | 同池同资源 | **H3** | 对照页 |
| 演示 | Streamlit / MCP | 可审计交付 | `run_console.ps1` |

---

## 3. 核心数学模型

### 3.1 决策变量

\[
x_{ib}\in\{0,1\}
\quad i\in\mathcal{P},\; b\in\mathcal{B}
\]

患者 \(i\) 是否分到床 \(b\)。\(B=|\mathcal{B}|\) 默认 20。

### 3.2 硬约束

\[
\begin{aligned}
\sum_i x_{ib}&\le 1 &&\forall b
&&\text{一床至多一人}\\
\sum_b x_{ib}&\le 1 &&\forall i
&&\text{一人至多一床}\\
x_{ib}&=0 && i\in\mathcal{I},\,b\notin\mathcal{B}_{\mathrm{iso}}
&&\text{隔离患者→隔离床}\\
\sum_{i\in\mathcal{V}}\sum_b x_{ib}&\le V &&
&&\text{呼吸机人数}\le V
\end{aligned}
\]

| 符号 | 默认参数 | 意义 |
|------|----------|------|
| \(B\) | `n_beds=20` | 总床位 |
| \(\|\mathcal{B}_{\mathrm{iso}}\|\) | `n_isolation_beds=4` | 隔离床数（床号 1–4） |
| \(V\) | `n_ventilators=8` | 呼吸机全局上限 |
| \(\mathcal{I},\mathcal{V}\) | 规则近似 | 隔离/呼吸机需求（非金标准） |

### 3.3 软目标（多目标向量）

高危阈值：\(\mathcal{H}=\{i:\mathrm{SOFA}_i\ge 10\}\)，`HIGH_RISK_SOFA=10`。

| 符号 | 键名 | 方向 | 公式 / 意义 |
|------|------|------|-------------|
| \(f_{\mathrm{occ}}\) | occupancy | max | \(\sum_{i,b}x_{ib}\) 占用床位数 |
| \(f_{\mathrm{hr}}\) | high_risk | max | \(\sum_{i\in\mathcal{H}}\sum_b x_{ib}\) 已收高危人数 |
| \(f_{\mathrm{pri}}\) | **wait** | max | \(\sum_{i,b} w_i x_{ib}\) 优先级总和（**≠候诊时间**） |
| \(f_{\mathrm{ov}}\) | overload | min | \(\sum_{i\in\mathcal{H},b\notin\mathrm{ISO}}\mathrm{SOFA}_i x_{ib}\) 高危落普通床 |
| \(f_{\mathrm{bal}}\) | balance | min | 各病区归一化占用率极差 |
| \(f_{\mathrm{zone}}\) | zone_mismatch | min | 病区错配次数 |
| \(f_{\mathrm{move}}\) | move | min | 滚动时换床次数 |

入模时 \(w_i\) 常按 `priority_weight × 1000` 取整。

### 3.4 加权和（旧基线算法）

\[
\max\;
\sum_k \mathrm{sign}_k\cdot c_k(\lambda_k)\cdot f_k
\]

\(c_k\) 为按目标上界归一化的整数系数，使 \(\lambda\) 表示相对重要性。

**当前 `lambda.*`（calib+eval 写回）：**

| 参数 | 默认值 | 意义 |
|------|--------|------|
| `occupancy` | **2.0** | 填床权重最大，优先提高占用 |
| `wait` | **0.5** | 优先级总和（键名易误解） |
| `overload` | **0.1** | 惩罚高危错配 |
| `balance` | **0.1** | 惩罚病区不均 |
| `zone_mismatch` | **0.1** | 惩罚病区不匹配 |
| `high_risk` | **0.0** | 加权和里暂不显式加权（高危靠 Lex/RFCC/显式目标） |

### 3.5 词典序 / ε-约束（对照机理）

**占用优先 Lex（默认序）：**  
occupancy ≻ high_risk ≻ wait ≻ overload ≻ …  
逐层求最优并等式锁定。

**ε-约束：** 主优化多为 `wait`，其余 \(f\ge\varepsilon\) 或 \(f\le\varepsilon\)；ε 可由 WS 解自适应。

### 3.6 新机制 RFCC（H7）

稀缺门控：若 \(n_{\mathrm{patients}}\ge n_{\mathrm{beds}}\)，

\[
\mathrm{high\_risk}\succ\mathrm{overload}\succ\mathrm{wait}\succ\mathrm{occupancy}\succ\cdots
\]

否则占用优先。代码：`objective_mode="clinical_cascade"`。

### 3.7 新指数 CARE / UHRM（H7）

\[
\mathrm{UHRM}=\sum_{i\in\mathcal{H},\,a_i=0}w_i
\]

\[
\mathrm{CARE}
=\frac{|\mathcal{H}\cap A|}{|\mathcal{H}|}
-\alpha\cdot\frac{f_{\mathrm{ov}}}{10\cdot\max(|\mathcal{H}\cap A|,1)}
-\beta\cdot\frac{\mathrm{UHRM}}{\sum_{i\in\mathcal{H}}w_i+\varepsilon}
\]

| 参数 | 默认 | 意义 |
|------|------|------|
| \(\alpha\) | 0.35 | 错配在 CARE 中的惩罚强度 |
| \(\beta\) | 0.35 | 未服务高危质量惩罚强度 |
| 10 | `HIGH_RISK_SOFA` | overload 归一化尺度 |

**CARE↑ 更好。**

### 3.8 紧迫度（预测层）

\[
u_i^{\mathrm{formula}}=1+\frac{\mathrm{SOFA}_i}{10}+\frac{2}{1+\max(\mathrm{LOS}_i,1)}
\]

GBDT 拟合该构造信号 → `feat.patient_priority`。`predict.priority_source`: `gbdt` | `sofa_rule`。

H5：同约束换 \(w_i\)，比分配集合 Jaccard \(J(A,B)=|A\cap B|/|A\cup B|\)。

---

## 4. 关键参数总表（按模块）

### 4.1 资源与求解

| 参数路径 | 默认 | 意义 |
|----------|------|------|
| `resources.n_beds` | 20 | 床位数 \(B\) |
| `resources.n_isolation_beds` | 4 | 隔离床 |
| `resources.n_ventilators` | 8 | 呼吸机上限 \(V\) |
| `resources.max_patients` | 200 | 候选上限（与 solver 配合） |
| `resources.bed_zones` | ISO/MICU/SICU/CCU/NICU 各 4 | 病区布局 |
| `solver.candidate_cap` | 1000 | CP-SAT 候选截断 |
| `solver.max_time_seconds` | 180 | 求解时限（秒） |
| `policy.default` | `cp_sat` | 生产默认策略 |

### 4.2 滚动

| 参数 | 默认 | 意义 |
|------|------|------|
| `rolling.step_hours` | 2 | 每步模拟小时数 |
| `rolling.admission_rate` | 0.05 | 每步相对床位的入院强度 |
| `rolling.discharge_rate` | 0.05 | 每步出院强度 |
| H6 `reoptimize` | true/false | 每步是否再跑 CP-SAT |

### 4.3 评测划分

| 参数 | 默认 | 意义 |
|------|------|------|
| `eval_split.calib_ratio` | 0.7 | 调参子集比例 |
| `eval_split.seed` | 42 | 可复现划分 |

**不是** train/val/test 口号，是 calib/eval。

### 4.4 PPO 对照轨（非默认）

| 参数 | 默认 | 意义 |
|------|------|------|
| `ppo.learning_rate` | 3e-4 | 学习率 |
| `ppo.gamma` | 0.99 | 折扣 |
| `ppo.gae_lambda` | 0.95 | GAE |
| `ppo.clip_range` | 0.2 | PPO clip |
| `ppo.batch_size` | 64 | 批大小 |
| `ppo.n_steps` | 256 | 每轮步数 |
| `ppo.total_timesteps` | 200000 | 总训练步 |
| `ppo.candidate_patients` | 20 | 对照池大小 |
| `rl.reward_weights.*` | 与 λ 同量级 | **与 CP-SAT λ 解耦**，防串调 |

### 4.5 病区布局（默认）

| 床号范围 | 区 | 意义 |
|----------|-----|------|
| 1–4 | ISO | 隔离 |
| 5–8 | MICU | 内科重症 |
| 9–12 | SICU | 外科重症 |
| 13–16 | CCU | 冠心 |
| 17–20 | NICU | 神经（本仓分区标签） |

---

## 5. 算法栈一览

| 层级 | 算法 / 模型 | 角色 | 是否「本仓具名创新」 |
|------|-------------|------|----------------------|
| 紧迫度 | SOFA 规则 · 构造公式 · GBDT | 预测 | 否（标准）；**H5 闭环验收**是贡献 |
| 分配 | CP-SAT 0-1 IP | 默认决策 | 否（工具） |
| 多目标 | WS / Lex / ε | 对照机理 | H4 对照协议 |
| **RFCC** | 稀缺门控风险优先级联 | 决策机制 | **是（H7）** |
| **CARE** | cover−α ov−β uhrm | 评价指标 | **是（H7）** |
| 滚动 | 滚动时域 + 再优化 | 动态 | H6 对照 |
| RL | MaskablePPO | 离线对照 | 否；禁 online 宣称 |

---

## 6. 演示与命令

```powershell
$env:PYTHONPATH = (Get-Location)
.\scripts\run_console.ps1
.\.venv\Scripts\python.exe -m application.run_method_bakeoff --candidate-patients 40
.\.venv\Scripts\python.exe -m application.run_pto_ablation --candidate-patients 40
.\.venv\Scripts\python.exe -m application.run_rolling_contrast --steps 8
```

---

## 7. 一页纸（投屏用）

1. **架构：** UI → L4 → domain(SOFA→CP-SAT→滚动) → MIMIC  
2. **创新核心：** RFCC + CARE（H7）；证据链 H3–H6  
3. **数学：** \(x_{ib}\) + 硬约束 + 多目标 \(f\)；RFCC 改序；CARE 公式  
4. **关键 λ：** occ=2.0, wait=0.5, overload/balance/zone=0.1  
5. **资源：** 20 床 / 4 隔离 / 8 呼吸机；高危阈值 SOFA≥10  
6. **默认：** `cp_sat`；不接 risk_score；不宣称 online PPO  
