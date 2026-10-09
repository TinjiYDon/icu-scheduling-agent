# 模型、算法与数学公式（答辩技术附录）

> 与报告词配套：[REPORT_SPEECH.md](REPORT_SPEECH.md) · 主线：[MASTER_NARRATIVE.md](MASTER_NARRATIVE.md)  
> 符号与代码一致：`domain/optimizer/cp_sat.py` · `multiobjective.py` · `predict_priority.py`

---

## 1. 决策变量与硬约束（分配模型）

设候选患者集合 \(\mathcal{P}=\{1,\ldots,n\}\)，床位集合 \(\mathcal{B}=\{1,\ldots,B\}\)。  
二元变量：

\[
x_{ib}\in\{0,1\}
\quad\text{表示患者 }i\text{ 是否分到床 }b。
\]

**硬约束（之前演示若只有「按分排序塞床」，通常没有完整写出）：**

\[
\begin{aligned}
\sum_{i\in\mathcal{P}} x_{ib} &\le 1 && \forall b\in\mathcal{B}
&&\text{（一床至多一人）}\\
\sum_{b\in\mathcal{B}} x_{ib} &\le 1 && \forall i\in\mathcal{P}
&&\text{（一人至多一床）}\\
x_{ib}&=0 && \forall i\in\mathcal{I},\; b\notin\mathcal{B}_{\mathrm{iso}}
&&\text{（隔离患者只能用隔离床）}\\
\sum_{i\in\mathcal{V}}\sum_{b} x_{ib} &\le V &&
\text{（需呼吸机患者总数 }\le\text{ 呼吸机台数 }V\text{）}
\end{aligned}
\]

其中 \(\mathcal{I}\) 为隔离需求集，\(\mathcal{B}_{\mathrm{iso}}\) 为隔离床，\(\mathcal{V}\) 为呼吸机需求集（规则近似，见 `constraint_rules.yaml`）。

求解器：**OR-Tools CP-SAT**（约束规划 + SAT，整数精确优化）。

---

## 2. 软目标（多目标向量）

记 \(a_i=\sum_b x_{ib}\)（患者 \(i\) 是否入院）。主要目标：

| 符号 | 名称 | 方向 | 定义（与代码一致） |
|------|------|------|-------------------|
| \(f_{\mathrm{occ}}\) | occupancy | max | \(\sum_{i,b}x_{ib}\) 占用床位数 |
| \(f_{\mathrm{hr}}\) | high_risk | max | \(\sum_{i\in\mathcal{H}}\sum_b x_{ib}\)，\(\mathcal{H}=\{i:\mathrm{SOFA}_i\ge 10\}\) |
| \(f_{\mathrm{pri}}\) | wait / priority_served | max | \(\sum_{i,b} w_i\,x_{ib}\)，\(w_i=\) 紧迫度（×1000 入模） |
| \(f_{\mathrm{ov}}\) | overload | min | \(\sum_{i\in\mathcal{H}}\sum_{b\notin\mathcal{B}_{\mathrm{iso}}}\mathrm{SOFA}_i\,x_{ib}\)（高危落非隔离床） |
| \(f_{\mathrm{bal}}\) | balance | min | 各病区归一化占用率极差 |
| \(f_{\mathrm{zone}},f_{\mathrm{move}}\) | zone / move | min | 病区错配、换床惩罚（滚动时） |

> **注意**：键名 `wait` **不是**墙钟等待时间，而是 priority 总和（语义披露）。

---

## 3. 三种多目标算法（同硬约束，换机理）

### 3.1 加权和（Weighted Sum）——旧基线仍保留

\[
\max\;
\lambda_{\mathrm{occ}}\tilde f_{\mathrm{occ}}
+\lambda_{\mathrm{hr}}\tilde f_{\mathrm{hr}}
+\lambda_{\mathrm{pri}}\tilde f_{\mathrm{pri}}
-\lambda_{\mathrm{ov}}\tilde f_{\mathrm{ov}}
-\lambda_{\mathrm{bal}}\tilde f_{\mathrm{bal}}
-\cdots
\]

\(\tilde f\) 为按上界归一化后的整数目标；\(\lambda\) 来自 `optimizer.yaml`。  
**这是「过去常见」做法：一组权重压成单目标。**

### 3.2 词典序（Lexicographic）——本仓明示层级

给定优先级序 \(f^{(1)}\succ f^{(2)}\succ\cdots\succ f^{(K)}\)（默认 occupancy → high_risk → wait → …）：

\[
\begin{aligned}
z_1^*&=\mathrm{opt}\;f^{(1)}\\
z_k^*&=\mathrm{opt}\;f^{(k)}
\quad\text{s.t.}\quad
f^{(j)}=z_j^*\quad(j<k),\quad
\text{硬约束}
\end{aligned}
\]

逐层锁最优值。若某层仅 FEASIBLE，标记 `exact_hierarchy=false`。  
**相对加权和：不再用 \(\lambda\) 偷偷决定「高危是否优先于占用」。**

### 3.3 ε-约束（Epsilon-constraint）——扫折中前沿

选主目标（如 \(\max f_{\mathrm{pri}}\)），其余变底线：

\[
\begin{aligned}
\max\quad & f_{\mathrm{pri}}\\
\text{s.t.}\quad
& f_{\mathrm{occ}}\ge\varepsilon_{\mathrm{occ}},\quad
f_{\mathrm{hr}}\ge\varepsilon_{\mathrm{hr}},\\
& f_{\mathrm{ov}}\le\varepsilon_{\mathrm{ov}},\quad
f_{\mathrm{bal}}\le\varepsilon_{\mathrm{bal}},\quad
\text{硬约束}
\end{aligned}
\]

\(\varepsilon\) 由 payoff 理想/劣解取中位或由可行参考解自适应（bake-off）。  
可对网格求非支配集并算 **Hypervolume**（阶段 3）。

---

## 4. 紧迫度模型（Predict 层）

对患者 \(i\)，SOFA 与住院时长 \(\mathrm{LOS}_i\)（小时）：

\[
\begin{aligned}
u_i^{\mathrm{sofa}}&=1+\frac{\mathrm{SOFA}_i}{10}\\[4pt]
u_i^{\mathrm{formula}}&=1+\frac{\mathrm{SOFA}_i}{10}+\frac{2}{1+\max(\mathrm{LOS}_i,1)}\\[4pt]
u_i^{\mathrm{gbdt}}&=\mathrm{clip}\big(\widehat{g}(\mathrm{SOFA}_i,\mathrm{careunit}_i,\mathrm{LOS}_i),\,1,5\big)
\end{aligned}
\]

\(\widehat{g}\) 为仓内 GBDT/GBR，监督信号用 \(u^{\mathrm{formula}}\) 构造（**不接**外部 risk_score）。  
写入 \(w_i\) 后进入 CP-SAT。

**H5：** 同硬约束下分别注入 \(u^{\mathrm{sofa}}/u^{\mathrm{formula}}/u^{\mathrm{gbdt}}\)，比较分配集合 Jaccard：

\[
J(A,B)=\frac{|A\cap B|}{|A\cup B|},\quad
A,B\subseteq\mathcal{P}\text{ 为已分床患者集合。}
\]

---

## 5. 滚动再优化（H6）

时间步 \(t=1,\ldots,T\)：出院 → 入院 →（可选）再求解。

- **滚动 CP-SAT**：每步对在床+候选再解，并用换床惩罚稳定已安置患者。  
- **旧/对照：贪心填空床**：不重解全局，只把队列头部塞进空床。

同随机种子对比时段平均 SOFA / 权重等。

---

## 6. 可选对照：MaskablePPO（非默认）

状态：床位占用与候选特征；动作：选患者/床（非法动作掩码）。  
奖励与 \(\lambda\) 对齐的加权项（见 `rl.reward_weights`）。  
**默认策略仍为 CP-SAT**；无轨迹协议不宣称 online MIMIC-PPO。

---

## 7. H7 新机制 RFCC + 新指数 CARE（具名创新）

详见 [H7_RFCC_CARE.md](H7_RFCC_CARE.md)。

**稀缺门控：** 若 \(n>B\)，词典序改为  
\(\mathrm{high\_risk}\succ\mathrm{overload}\succ\mathrm{wait}\succ\mathrm{occupancy}\succ\cdots\)；  
否则占用优先。

**UHRM / CARE：**

\[
\mathrm{UHRM}=\sum_{i\in\mathcal{H},a_i=0}w_i,\quad
\mathrm{CARE}=\mathrm{cover}-\alpha\cdot\mathrm{ov\_norm}-\beta\cdot\mathrm{uhrm\_norm}.
\]

## 8. 「以前没有 → 现在有」对照（公式视角）

| 以前常见 | 对应公式/做法 | 现在多出来的 |
|----------|---------------|--------------|
| 只按分数排序塞床 | 无完整 \(x_{ib}\) 硬约束 | 完整 CP-SAT 硬约束组 |
| 只调一组 \(\lambda\) / 占用优先 Lex | §3.1–3.2 | **H7 RFCC** 稀缺门控风险优先级联 |
| 无综合临床指数 | 原始 \(f\) 分项 | **CARE / UHRM** |
| 只报优先级相关 | Spearman | **H5** Jaccard |
| 滚动无对照 | 动画 | **H6** |
| 各抽各池 | 不可比 | Fair 同池 |
