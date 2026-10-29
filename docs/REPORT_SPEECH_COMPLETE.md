# 完整报告词（H7 着重 · 全要素版 · 约 10 分钟）

> 用途：正式汇报 / 答辩主讲 · **先讲新机制与新指数，再收束全链**  
> 技术附录：[H7_RFCC_CARE.md](H7_RFCC_CARE.md) · [MODEL_FORMULAS.md](MODEL_FORMULAS.md) · [MASTER_NARRATIVE.md](MASTER_NARRATIVE.md)  
> **禁区**：不说发明了新 CP 求解器；不说 online MIMIC-PPO；不说全面超越医院现网

---

## 【开场 · 40 秒】一句话定位

各位老师好。

本项目做的是 **ICU 床位资源的动态调度**。  
总目标六个字：**可审计、可对照、可滚动**。

今天汇报请老师抓住一条主线：

> **在 MIMIC 可复现设定下，用可解释的硬约束分床；相对「只调权重 / 占用优先词典序」，我们提出具名的新机制 RFCC 与新指数 CARE/UHRM，并在同池对照中验收。**

边界先说清：独立调度仓，**不读**预警项目 risk_score；强化学习只作离线对照，**不宣称** online MIMIC-PPO。

---

## 【第一部分 · 着重 · 3 分钟】新机制 RFCC + 新指数 CARE

这是本次最想强调的创新，请允许我先讲透。

### 1. 以前缺什么

常见做法有三种：按分数排序塞床；一组 λ 加权和；或者占用优先的词典序——**先尽量填满床，再谈别的**。  
ε-约束可以扫折中，但**不会**因为「人比床多」自动改成临床风险优先。  
评价上往往只报占用人数、等待类指标，**缺少一个把「高危覆盖、错配、没服务到的高危质量」捏在一起的指数**。

### 2. 新机制：RFCC

**全称：** Scarcity-Triggered Risk-First Clinical Cascade  
**中文：** 稀缺触发的风险优先临床级联  
**代码：** `objective_mode="clinical_cascade"`

规则很简单、但和旧法不同：

- 当候选病人数 **≥** 床位数（稀缺 / 一人一坑都要掂量）时，优化顺序变为：  
  **① 最大化高危（SOFA≥10）覆盖 → ② 最小化高危错配 overload → ③ 最大化优先级总和 → ④ 再尽量填满床……**  
- 当床位明显充裕时，才退回经典的「先填床」。

也就是说：**不是换了一个求解器，而是换了一套面向 ICU 的决策门控与层级。**  
稀缺时先保「危重有床、尽量别把高危塞错床型」，再谈填满率——这是临床直觉，却是占用优先 Lex 里没有写死的机制。

### 3. 新指数：UHRM 与 CARE

**UHRM（Unserved High-Risk Mass）**——未服务高危质量：

\[
\mathrm{UHRM}=\sum_{i\in\mathcal{H},\,a_i=0} w_i
\]

没上床的高危病人，其优先级权重加总；越大说明「该保的危重质量」漏得越多。

**CARE（Clinical Allocation Risk-Equity）**——临床分配风险-公平指数：

\[
\mathrm{CARE}
=\mathrm{cover}
-\alpha\cdot\mathrm{overload\_norm}
-\beta\cdot\mathrm{uhrm\_norm}
\]

- cover：高危池里被收治的比例  
- overload_norm：高危落在非隔离床等错配强度  
- uhrm_norm：UHRM 相对高危池总权重的比例  

默认 α=β=0.35。**CARE 越高越好**：多收高危、少错配、少浪费高危优先级。  
每次求解写入 `evaluation.care` / `care_index`，bake-off 里与加权和、词典序、ε 同池对照。

### 4. 答辩一句话（请记住）

> 我们提出 **RFCC 稀缺触发风险优先级联**，并定义 **CARE/UHRM** 指数；相对只调 λ 或占用优先 Lex，这是本仓的**具名新机制与新指标**。

---

## 【第二部分 · 1 分钟】约束（规矩）

**业务约束：** 一人一床；隔离患者进隔离床；呼吸机人数有上限；隔离/呼吸机需求目前是可配置规则近似，解释里披露，不装临床金标准。

**研究约束：** 默认 CP-SAT 保可解释；对比必须 Fair（同 stay_ids、同资源）；禁止硬接外部 risk_score；无轨迹不宣称 online PPO。

**语义约束：** 键名 `wait` 是优先级总和，不是候诊分钟；`overload` 是高危落非隔离床的 SOFA 累加。

约束说清楚，本身也是诚实贡献。

---

## 【第三部分 · 1 分钟】总目标与总内容（一条链）

总目标：**可审计 · 可对照 · 可滚动**。

总内容链：

**MIMIC → 仓内 SOFA/GBDT 紧迫度 → 硬约束 CP-SAT →（WS / Lex / ε / RFCC）→ 滚动再优化 → Fair 对照与演示。**

H7 挂在「多目标决策」这一环上：同一套硬约束，换 RFCC 机理，并用 CARE 评价。

完成后的意义：可解释试算 + 可复现研究协议；不是明天替换值班医生。

---

## 【第四部分 · 1.5 分钟】和过去比还多了什么（H4–H6）

在 RFCC/CARE 之外，证据链还包括：

| 相对过去 | 现在有的 |
|----------|----------|
| 只调一组 λ | 同约束下 WS / Lex / ε 对照（H4） |
| 只报分数相关 | 换紧迫度后比分床名单 Jaccard（H5） |
| 滚动只是动画 | 再优化 vs 贪心填床对照（H6） |
| 各方法各抽一批人 | Fair 同池同资源（H3） |

本地 H5 曾见 SOFA-only 与公式分配集合 Jaccard≈0.11——预测层差异会改谁上床。  
小池指标打平也如实写，不硬吹。

---

## 【第五部分 · 2 分钟】模型、算法与公式（含 H7）

### 决策变量与硬约束

\(x_{ib}\in\{0,1\}\)：患者 \(i\) 分到床 \(b\)。  
一人一床、一床一人、隔离床限制、呼吸机上限。求解器：OR-Tools **CP-SAT**（工具，不是创新本身）。

### 软目标向量

\[
\begin{aligned}
f_{\mathrm{occ}}&=\sum x_{ib} &&\text{占用↑}\\
f_{\mathrm{hr}}&=\sum_{i:\mathrm{SOFA}_i\ge10}\sum_b x_{ib} &&\text{高危人数↑}\\
f_{\mathrm{pri}}&=\sum w_i x_{ib} &&\text{优先级和↑（键名 wait）}\\
f_{\mathrm{ov}}&=\sum_{\substack{i\in\mathcal{H}\\b\notin\mathrm{ISO}}}\mathrm{SOFA}_i x_{ib} &&\text{错配↓}
\end{aligned}
\]

### 算法怎么用这些目标

- **加权和：** \(\max\sum\lambda_k\tilde f_k\)（旧基线）  
- **占用优先 Lex / ε：** 教科书多目标（对照）  
- **RFCC（新）：** 稀缺门控下 high_risk → overload → wait → occupancy…  

紧迫度：

\[
u_i=1+\frac{\mathrm{SOFA}_i}{10}+\frac{2}{1+\max(\mathrm{LOS}_i,1)}
\]

GBDT 仓内拟合；不接外部 risk。

---

## 【第六部分 · 1 分钟】价值 · 实用 · 学术立场

**价值：** 管理侧能问「为什么这张床」；研究侧可在同一协议上换模型；CARE 让「保高危做得好不好」可量化。

**实用：** 课设/答辩演示、离线试算——可用；医院正式上线、在线 RL——未就绪、未宣称。

**学术：**  
- 立得住：MIMIC 设定、可复现、Fair 对照、具名机制与指数可证伪。  
- 须谦虚：未发明新通用求解器；隔离/呼吸机需求仍是启发式；无床旁 RCT。  
- 立场：应用运筹与可复现系统研究——**创新主张是 RFCC + CARE，不是「我们用了谷歌库」。**

---

## 【证据 · 40 秒】怎么证明不是空口

- `clinical_cascade` + `evaluation.care` / UHRM  
- `python -m application.run_method_bakeoff`（含 greedy / WS / Lex / ε / **RFCC**）  
- H5 `run_pto_ablation` · H6 `run_rolling_contrast`  
- Streamlit：多目标页、对照页；`.\scripts\run_console.ps1`  
- 文档：`H7_RFCC_CARE.md` · `REPORT_SPEECH_COMPLETE.md`  
- GitHub：`icu-scheduling-agent` · **PR #16**

---

## 【收尾 · 30 秒】把重点收回来

请允许我用七句话收束：

1. **问题**：ICU 分床是硬约束下的动态分配，不是排序题。  
2. **目标**：可审计、可对照、可滚动。  
3. **着重创新**：RFCC 新机制 + CARE/UHRM 新指数。  
4. **证据链**：H4–H6 的机理对照、预测→决策、滚动与 Fair 评测。  
5. **模型**：\(x_{ib}\) CP-SAT + 多目标向量 + 仓内紧迫度。  
6. **价值**：可解释试算与可复现协议；上线仍需临床工程。  
7. **立场**：对标文献、不冒充 SOTA，用可复现结果说话。

以上是完整汇报。请各位老师批评指正，谢谢。

---

## 附：三问应急

| 问 | 答 |
|----|-----|
| 创新到底是什么？ | **RFCC 机制 + CARE/UHRM 指数**；其余是证据链与平台。 |
| 是不是拼了 OR-Tools？ | 库是工具；稀缺门控风险优先级联与 CARE 是我们的主张。 |
| 学术够不够？ | 不够当顶会新求解器；够主张场景化机制与指标 + 可复现对照。 |
