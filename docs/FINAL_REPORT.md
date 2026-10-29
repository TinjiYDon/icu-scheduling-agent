# ICU 床位动态调度 · 完整汇报稿（面面俱到 · 约 12–15 分钟）

> **本页 = 答辩/课题汇报唯一主讲稿**（可直接照着念）  
> 技术附录：[ARCHITECTURE_INNOVATION_MATH.md](ARCHITECTURE_INNOVATION_MATH.md) · [H7_RFCC_CARE.md](H7_RFCC_CARE.md) · [MODEL_FORMULAS.md](MODEL_FORMULAS.md)  
> 主线：[MASTER_NARRATIVE.md](MASTER_NARRATIVE.md) · 精简口播：[REPORT_SPEECH_COMPLETE.md](REPORT_SPEECH_COMPLETE.md)  
> GitHub：`icu-scheduling-agent` · PR #16  
> **禁区**：不宣称发明新 CP 求解器；不宣称 online MIMIC-PPO；不宣称全面超越医院现网；不接 decision `risk_score`

---

## 〇、开场（约 1 分钟）

各位老师好。

我汇报的课题是：**ICU 医疗资源（床位）动态调度智能体**，仓库名 `icu-scheduling-agent`。

ICU 一紧张，值班要同时想：谁更危重、隔离床够不够、呼吸机够不够、病区挤不挤、过一会儿又有人出又有人进——**这不是排个名次就能结束，而是带硬约束的动态资源分配问题。**

请老师先记住总目标六个字：

### **可审计 · 可对照 · 可滚动**

以及今天最想强调的一句创新主张：

> **在 MIMIC 可复现设定下，用可解释硬约束做分床；相对「只调权重 / 占用优先词典序」，我们提出具名新机制 RFCC 与新指数 CARE/UHRM，并在同池对照中验收。**

边界三句话：  
① 本课题**独立**，不读取预警项目的 risk_score；  
② 默认策略是 **CP-SAT**，强化学习只作离线对照；  
③ **不宣称**已经在 MIMIC 床旁 online 学会调度。

下面按：**背景与目标 → 约束 → 架构 → 模型算法与参数 → 具名创新 H7 → 证据链 H3–H6 → 价值实用学术 → 演示与收尾** 汇报。

---

## 一、问题背景与总目标、总内容（约 1.5 分钟）

### 1.1 要解决什么

在公开 MIMIC 数据可复现设定下，对 ICU 候选患者做**床位分配**：满足隔离/呼吸机等硬约束，权衡占用、高危覆盖、优先级、错配等目标，并支持随入出转**滚动再决策**。

### 1.2 总目标（可检查）

| 子目标 | 人话 | 怎么验收 |
|--------|------|----------|
| 可审计 | 为什么这张床给这个人能说清 | explain + 硬约束 + 默认 cp_sat |
| 可对照 | 换方法必须同批人、同一套床 | Fair stay_ids + 同资源 |
| 可滚动 | 入出转变了还能再决策 | simulate / H6 对照 |

### 1.3 总内容（一条链，不散讲功能清单）

```text
MIMIC Layer1
    → 仓内 SOFA / GBDT 紧迫度 w_i
    → 硬约束 CP-SAT 分床 x_ib
    → 多目标：加权和 / 词典序 / ε / 【RFCC 新机制】
    → 滚动再优化
    → Fair 对照 + CARE 指数 + Streamlit / MCP 演示
```

完成后的意义：交出**可解释试算与可复现研究协议**，不是明天替换值班医生。

---

## 二、约束（约 1 分钟）

没有约束的「智能」不可信。我们分三层。

### 2.1 业务约束

- 一人一床、一床一人；  
- 隔离患者只能进隔离床；需呼吸机人数 ≤ 台数；  
- 隔离/呼吸机「谁需要」目前是**可配置规则近似**，解释报告披露——**不装临床金标准**。

### 2.2 研究约束

- 生产默认 **CP-SAT**；  
- 对比必须 **Fair**（同 stay_ids、同床位/隔离/呼吸机/分区）；  
- **禁止**硬接外部 risk_score；  
- 无轨迹协议 **不宣称** online PPO。

### 2.3 语义约束（避免听错）

- 目标键 `wait` = 已服务**优先级总和**，**不是**候诊分钟；  
- `overload` = 高危（SOFA≥10）落到**非隔离床**的 SOFA 累加。

约束说清楚，本身也是学术诚实。

---

## 三、系统架构（约 1.5 分钟）

### 3.1 分层

| 层 | 目录 | 职责 |
|----|------|------|
| 展示 | `presentation/` | Streamlit Ops 台、MCP `optimize_beds` |
| 应用 L4 | `application/` | plan、simulate、多目标/对照 UI、bake-off、H5/H6 CLI |
| 领域 | `domain/` | SOFA/GBDT、CP-SAT、RFCC、CARE、滚动、RL 对照 |
| 数据 | `data_access/` + dump | MIMIC Layer1（约 9.4 万 stays/SOFA） |

### 3.2 架构环 ↔ 创新挂点

| 架构环 | 创新 |
|--------|------|
| 紧迫度 | H5：换 \(w_i\) 看分床名单变不变 |
| 硬约束分床 | H1：规则可配置可披露 |
| WS / Lex / ε | H4：同约束机理对照 |
| **RFCC** | **H7：新机制** |
| **CARE/UHRM** | **H7：新指数** |
| 滚动 | H6：再优化 vs 贪心填床 |
| Fair 评测 | H3：同池同资源 |

默认 `policy.default=cp_sat`。PPO 在 `domain/rl`，默认不启用。

---

## 四、数学模型与关键算法（约 3 分钟）

### 4.1 决策变量

\[
x_{ib}\in\{0,1\}
\quad\text{患者 }i\text{ 是否分到床 }b
\]

### 4.2 硬约束

\[
\sum_i x_{ib}\le 1,\quad
\sum_b x_{ib}\le 1,\quad
\text{隔离患者}\to\text{隔离床},\quad
\text{需呼吸机人数}\le V
\]

求解器：**OR-Tools CP-SAT**（工具，不是创新本身）。

### 4.3 软目标向量

高危集 \(\mathcal{H}=\{i:\mathrm{SOFA}_i\ge 10\}\)。

| 符号 | 键名 | 方向 | 意义 |
|------|------|------|------|
| \(f_{\mathrm{occ}}\) | occupancy | max | 占用床位数 |
| \(f_{\mathrm{hr}}\) | high_risk | max | 已收高危人数 |
| \(f_{\mathrm{pri}}\) | wait | max | \(\sum w_i x_{ib}\) 优先级总和 |
| \(f_{\mathrm{ov}}\) | overload | min | 高危落非隔离床的 SOFA 累加 |
| \(f_{\mathrm{bal}}\) 等 | balance / zone / move | min | 均衡、错配、换床 |

### 4.4 三种（旧）多目标算法 + 本仓新机制

**（1）加权和（基线）**

\[
\max\sum_k \lambda_k\,\tilde f_k
\]

**当前关键 λ（`optimizer.yaml`，calib+eval 写回）：**

| 参数 | 值 | 意义 |
|------|-----|------|
| occupancy | **2.0** | 填床最重要 |
| wait | **0.5** | 优先级总和 |
| overload / balance / zone_mismatch | **0.1** | 错配与结构惩罚 |
| high_risk | **0.0** | 加权和里不显式加；高危靠 Lex/RFCC |

**（2）占用优先词典序：** 先填床，再高危，再 priority……（教科书）  

**（3）ε-约束：** 主优化 wait，其余目标变底线，可扫 Pareto / Hypervolume。

**（4）RFCC——见第五节（着重）。**

### 4.5 紧迫度（预测层）

\[
u_i=1+\frac{\mathrm{SOFA}_i}{10}+\frac{2}{1+\max(\mathrm{LOS}_i,1)}
\]

GBDT 仓内拟合 → \(w_i\)；`predict.priority_source` = gbdt | sofa_rule。

### 4.6 资源与求解关键参数（务必会背）

| 参数 | 默认 | 意义 |
|------|------|------|
| n_beds | 20 | 总床 \(B\) |
| n_isolation_beds | 4 | 隔离床（床 1–4） |
| n_ventilators | 8 | 呼吸机上限 \(V\) |
| HIGH_RISK_SOFA | 10 | 高危阈值 |
| solver.max_time_seconds | 180 | 求解时限 |
| candidate_cap | 1000 | 候选截断 |
| rolling.step_hours | 2 | 滚动步长 |
| admission/discharge_rate | 0.05 | 入出转强度 |
| eval_split.calib_ratio | 0.7 | calib/eval（不是 train/test） |

病区：ISO / MICU / SICU / CCU / NICU 各约 4 床。

---

## 五、具名创新（着重 · 约 3 分钟）——RFCC + CARE

这是汇报的核心，请老师重点听。

### 5.1 过去缺什么

- 排序塞床，或只调一组 λ；  
- 占用优先 Lex：**先填满再谈危重**；  
- ε 不会因「人≥床」自动改成风险优先；  
- 缺少把「高危覆盖 + 错配 + 未服务高危质量」合成一个指数。

### 5.2 新机制 RFCC

**全称：** Scarcity-Triggered Risk-First Clinical Cascade  
**中文：** 稀缺触发的风险优先临床级联  
**代码：** `objective_mode="clinical_cascade"`

- 当 \(n_{\mathrm{patients}}\ge n_{\mathrm{beds}}\)：  
  **高危覆盖 → 最小化 overload → 优先级总和 → 再填床……**  
- 床充裕：才退回占用优先。

**不是新求解器，是面向 ICU 的决策门控与层级。**

### 5.3 新指数 UHRM 与 CARE

\[
\mathrm{UHRM}=\sum_{i\in\mathcal{H},\,a_i=0}w_i
\quad\text{（没上床的高危优先级质量）}
\]

\[
\mathrm{CARE}=\mathrm{cover}-\alpha\cdot\mathrm{ov\_norm}-\beta\cdot\mathrm{uhrm\_norm}
\]

α=β=**0.35**。CARE **越高越好**。每次求解写入 `evaluation.care`。

### 5.4 创新一句话（请记下）

> 我们提出 **RFCC 稀缺触发风险优先级联**，并定义 **CARE/UHRM** 指数；相对只调 λ 或占用优先 Lex，这是本仓的**具名新机制与新指标**。

---

## 六、其余证据链 H3–H6（约 1.5 分钟）

| 编号 | 内容 | 作用 |
|------|------|------|
| H4 | 同硬约束 WS/Lex/ε 对照 + bake-off | 证明「换机理」不是换 logo |
| H5 | 换 SOFA/公式/GBDT，比分配 Jaccard | 预测必须接到决策（本地曾见 ≈0.11） |
| H6 | 滚动再优化 vs 只往空床塞 | 滚动不是摆设 |
| H3 | Fair 同池同资源贪心/CP/PPO | 评测纪律；小池打平如实报 |

Bake-off 现含：greedy · WS · Lex · ε · **clinical_cascade（RFCC）**，并输出 CARE。

---

## 七、价值、实用性、学术立场（约 1.5 分钟）

### 7.1 价值

- **管理/演示：** 能问「为什么这张床」；压力场景可试算；Streamlit + MCP。  
- **研究：** 同一协议上可换紧迫度或机理；CARE 量化「保高危好不好」。  
- **一句话：** 不是又一个调 OR-Tools 的作业，而是可解释、可对照的分床平台 + 具名机制指标。

### 7.2 实用性

| 场景 | 状态 |
|------|------|
| 课设/答辩演示 | 可用 |
| 离线 MIMIC 试算 | 可用（restore dump） |
| 医院正式上线 | 未就绪 |
| 在线 RL 调度 | 未宣称 |

### 7.3 学术权威性（谦虚但站得住）

**立得住：** MIMIC 公开设定；运筹/多目标有文献锚点；假设可证伪；Fair 评测；RFCC/CARE 可命名可对照。  

**须谦虚：** 未发明新通用求解器；隔离/呼吸机需求仍是启发式；无床旁 RCT；不宣称 SOTA。  

**立场：** 应用运筹与可复现系统研究——创新主张是 **RFCC + CARE**，证据链是 H3–H6，工具是 CP-SAT。

相对近刊（如 SciRep 2023 ICU 多目标 NSGA-II）：他们强在不确定下元启发式；我们切口是**精确可审计 CP-SAT + MIMIC 管道 + RFCC/CARE + Fair 协议**。

---

## 八、演示与证据入口（约 40 秒）

```powershell
.\scripts\run_console.ps1
# 导航：项目 → 运行 → 多目标 → 对照 → 验收

$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m application.run_method_bakeoff --candidate-patients 40
.\.venv\Scripts\python.exe -m application.run_pto_ablation --candidate-patients 40
.\.venv\Scripts\python.exe -m application.run_rolling_contrast --steps 8
```

文档：`FINAL_REPORT.md`（本稿）· `H7_RFCC_CARE.md` · `ARCHITECTURE_INNOVATION_MATH.md` · `STATUS.md`  
仓库 PR #16。

---

## 九、收尾（约 40 秒）

请允许用十条收束，面面俱到：

1. **问题**：ICU 分床是硬约束动态分配，不是排序题。  
2. **目标**：可审计、可对照、可滚动。  
3. **约束**：业务硬约束 + Fair 评测 + 语义披露 + 禁 risk/online 乱宣称。  
4. **架构**：UI→L4→domain→MIMIC，默认 CP-SAT。  
5. **模型**：\(x_{ib}\) + 多目标向量 \(f\) + 仓内紧迫度 \(w_i\)。  
6. **参数**：20 床/4 隔离/8 呼吸机；λ 以 occupancy=2.0、wait=0.5 为主；SOFA≥10 为高危。  
7. **着重创新**：RFCC 新机制 + CARE/UHRM 新指数。  
8. **证据链**：H3–H6 的 Fair、机理、PtO、滚动对照。  
9. **价值**：可解释试算与可复现协议；上线仍需临床工程。  
10. **立场**：对标文献、不冒充 SOTA，用可复现结果说话。

以上是完整汇报。请各位老师批评指正。谢谢。

---

## 附录 A · 三问应急

| 提问 | 应答 |
|------|------|
| 创新到底是什么？ | **RFCC + CARE/UHRM**；其余是平台与证据链。 |
| 是不是拼了 OR-Tools？ | 库是工具；稀缺门控风险优先级联与 CARE 是主张。 |
| 学术够不够？ | 不够当顶会新求解器；够主张场景化机制与指标 + 可复现对照。 |
| 约束是不是太简单？ | 硬约束故意可解释；难在权衡；需求启发式已披露。 |
| 和预警项目什么关系？ | 零耦合，不读 risk_score。 |

## 附录 B · 投屏文件清单

| 需要展示时 | 打开 |
|------------|------|
| 本稿口播 | `docs/FINAL_REPORT.md` |
| 架构参数表 | `docs/ARCHITECTURE_INNOVATION_MATH.md` |
| H7 专页 | `docs/H7_RFCC_CARE.md` |
| 公式板书 | `docs/MODEL_FORMULAS.md` |
| 状态数字 | `docs/STATUS.md` |
| 可视化看板 | Cursor Canvas：architecture-innovation-math |
