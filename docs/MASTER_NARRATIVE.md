# 总目标 · 总内容（一条主线串全仓）

> **本页是叙事 SSOT**：答辩、组员、Agent、文档索引都先对齐这里。  
> 更新：2026-10-09 · 细节数字见 [STATUS.md](STATUS.md) · 够格判断见 [ACADEMIC_VALUE.md](ACADEMIC_VALUE.md)

---

## 一、总目标（只记这一句）

**在 MIMIC 可复现设定下，做一个「可审计、可对照、可滚动」的 ICU 床位动态调度系统：  
用仓内病情紧迫度驱动硬约束优化，默认 CP-SAT；用公平协议证明多目标机理、预测→决策与滚动再优化的价值；不接外部预警风险分，不宣称未经验证的 online RL。**

拆成三个可检查子目标：

| 子目标 | 人话 | 怎么验收 |
|--------|------|----------|
| **可审计** | 为什么这张床给这个人，能说清 | explain + 硬约束 + 默认 `cp_sat` |
| **可对照** | 换方法/换紧迫度/换滚动策略，同池可比 | Fair stay_ids+资源 · H3–H6 · bake-off |
| **可滚动** | 入出转变化后能再决策，不是一次性静态表 | `simulate` / H6 · 轨迹协议（RL 另轨） |

**完成后的意义：** 不是「发明了新求解器」，而是交出一套可复现的 ICU 分床研究与演示平台——医院侧能解释，学术侧能对照，后续人能在同一协议上换模型。

---

## 二、总内容（一条链，按数据流）

所有模块都挂在这条链上，**不要按「功能清单」散讲**：

```text
MIMIC dump / Layer1
        ↓
   SOFA 时序 + 仓内 GBDT 紧迫度     ←── H5：换紧迫度看分床变不变
        ↓
   硬约束 CP-SAT 分床               ←── H1：规则可配置+披露
   （隔离床 / 呼吸机 / 分区）
        ↓
   多目标决策机理                   ←── H4：加权 / 词典序 / ε
   （同一套硬约束）                      + 方法 bake-off（vs 贪心）
        ↓
   滚动时域再优化                   ←── H2 到达强度 · H6 再优化 vs 贪心填床
        ↓
   公平评测 + 可选 PPO 离线对照     ←── H3 / S3（无轨迹不宣称 online）
        ↓
   Streamlit / MCP / 老师口径       ←── DEMO · TEACHER_PLAIN
```

```mermaid
flowchart LR
  A[MIMIC Layer1] --> B[SOFA / GBDT 紧迫度]
  B --> C[CP-SAT 硬约束分床]
  C --> D[多目标机理 H4]
  D --> E[滚动再优化 H6]
  E --> F[Fair 对照 H3]
  B -.->|H5 PtO| C
  F --> G[Streamlit / MCP / 答辩]
```

### 链上每一环「是什么 / 不是什么」

| 环 | 是什么 | 不是什么 |
|----|--------|----------|
| 紧迫度 | 仓内 SOFA + GBDT → `priority_weight` | decision 的 `risk_score` |
| 分床 | OR-Tools CP-SAT 硬约束分配 | 「用了谷歌库所以创新」 |
| 多目标 | 换决策机理（WS/Lex/ε） | 只调一组 λ 蒙一个折中解 |
| 滚动 | 每步可再求解 | 纯展示动画 |
| PPO | 同池离线对照 | MIMIC 床旁 online 已学会 |
| UI/MCP | 把链跑通给人看 | 产品级 HIS 替代 |

---

## 三、创新点如何挂在总目标上（别单列炫技）

| 假设 | 挂在哪一环 | 一句话贡献 | 入口 |
|------|------------|------------|------|
| H1 | 硬约束 | 需求规则可配置、可解释披露 | `constraint_rules.yaml` · explain |
| H2 | 滚动 | MIMIC 可校准到达，不是乱填费率 | intensity / rolling |
| H3 | 评测 | 同池同资源才谈贪心/CP/PPO | 对照页 · `compare_policies` |
| H4 | 多目标 | 三种机理对照，不是只调 λ | 多目标页 · MOO CLI |
| bake-off | 多目标+评测 | 专门答「是不是拼 OR-Tools」 | `run_method_bakeoff` |
| **H5** | 紧迫度→分床 | 相关性不够，要看名单 Jaccard | `run_pto_ablation` |
| **H6** | 滚动 | 再优化 vs 只往空床塞人 | `run_rolling_contrast` |

详细够格与文献位置：[ACADEMIC_VALUE.md](ACADEMIC_VALUE.md) · [SOTA_SURVEY.md](SOTA_SURVEY.md)

---

## 四、对外怎么用这一条线讲（3 分钟骨架）

1. **总目标**：可审计、可对照、可滚动的 ICU 分床。  
2. **顺着链指一遍**：数据 → 紧迫度 → CP-SAT → 三种多目标 → 滚动 → 对照台。  
3. **被质疑时**：  
   - 太简单？→ 硬约束故意可解释；难在权衡与对照。  
   - 拼接？→ 工程必拼接；贡献在协议与机理对照（H4–H6）。  
   - 学术价值？→ 平台 + 证据，不宣称算法 SOTA。  
4. **收尾**：默认 CP-SAT；PPO 离线；不接 decision 风险分。

口播细稿：[DEMO_SCRIPT.md](DEMO_SCRIPT.md) · 大白话：[TEACHER_PLAIN.md](TEACHER_PLAIN.md)

---

## 五、文档与代码地图（按主线查，不按文件名翻）

| 你想了解 | 先读 | 再跑 / 再看 |
|----------|------|-------------|
| 总目标（本页） | **MASTER_NARRATIVE** | — |
| 现在做到哪 | [STATUS.md](STATUS.md) | Streamlit |
| 下一步 | [ROADMAP.md](ROADMAP.md) · [TOP_TIER_NEXT.md](TOP_TIER_NEXT.md) | — |
| 参数语义（wait≠等待时长） | [PARAM_STORY.md](PARAM_STORY.md) | explain |
| 多目标细节 | [S2_MULTI_OBJECTIVE.md](S2_MULTI_OBJECTIVE.md) | `run_moo_phase3/4` |
| 数据 / restore | [DUMP_READY.md](DUMP_READY.md) | restore 脚本 |
| 老师创新口径 | [TEACHER_INNOVATION.md](TEACHER_INNOVATION.md) | DEMO |
| Agent 契约 | 根目录 `AGENTS.md` | pytest 白名单 |

**关键命令（顺着链）：**

```powershell
$env:PYTHONPATH = (Get-Location)
# 紧迫度消融（相关）
.\.venv\Scripts\python.exe -m application.compare_priority
# 分床 + 多目标 bake-off
.\.venv\Scripts\python.exe -m application.run_method_bakeoff --candidate-patients 20
# 预测→决策（H5）
.\.venv\Scripts\python.exe -m application.run_pto_ablation --candidate-patients 40
# 滚动增益（H6）
.\.venv\Scripts\python.exe -m application.run_rolling_contrast --steps 8
# 滚动仿真主路径
.\.venv\Scripts\python.exe -m application.simulate
# 演示台
.\scripts\run_console.ps1
```

---

## 六、禁区（任何讲法都不能破）

1. 不把 `icu-decision-agent` 的 `risk_score` 接进 `priority_weight`。  
2. 无轨迹协议 / 无床旁设定，不宣称 online MIMIC-PPO。  
3. 不说「用了 OR-Tools / 训练了 PPO」等于学术创新。  
4. 小池指标打平就承认打平——打平也是对照结论。

---

## 七、给 Agent / 组员的一句话

> 改任何功能前先问：它加强「可审计 / 可对照 / 可滚动」哪一条？若三条都不沾，默认不做。
