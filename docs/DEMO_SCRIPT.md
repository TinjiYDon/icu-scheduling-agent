# 答辩演示口播（5–7 分钟）

> 启动：`.\scripts\run_console.ps1` → http://localhost:8502  
> 前置：已 restore scheduling P0 dump（见 [`DUMP_READY.md`](DUMP_READY.md)）  
> 默认策略 **cp_sat**；**勿宣称** MIMIC 床旁 online PPO  
> 创新口径对照：[`TEACHER_INNOVATION.md`](TEACHER_INNOVATION.md)

导航顺序建议：**项目 → 运行 → 多目标 → 对照 → 验收**（「方法」可作备用）。

## 禁区话术（随时可用）

- 「骨干是可审计的 CP-SAT 硬约束，不是把 OR-Tools 当创新。」
- 「多目标是换决策机理（加权 / 词典序 / ε），不是只调一组 λ。」
- 「PPO 是同池离线对照；没有床旁 online 轨迹就不说 online RL。」

## 流程

### 1. 项目（约 40s）

- 一句话：ICU 候选池 → 仓内 SOFA/GBDT 优先级 → CP-SAT 分床 → 滚动评估。  
- 强调：**独立仓**，不读 decision 风险分；默认 **CP-SAT**。

### 2. 运行（约 2min）

- 首次进入常会自动跑一次（侧栏可关）。  
- 点 KPI：求解状态、占用/利用率、**高危分配率**、**Zone 匹配率**。  
- 看占用时序 / 热力 / 在床平均 SOFA；分配表可按高 SOFA 扫一眼。  
- 展开可解释：目标分解 + 若干条分配理由。  
- 侧栏策略若切到 PPO：说明「研究对照，观测维与训练床位绑定」。

### 3. 多目标（约 2min）· H4

- 三句话讲清机理：  
  - **加权和**：一组 λ，一个折中解（基线）。  
  - **词典序**：先占床，再高危，再优先级总和。  
  - **ε-约束**：其余目标变底线，便于扫 Pareto。  
- 若有 `reports/moo/summary_latest.json`：指网格点数 / 可行 / 非支配 / HV。  
- 若有场景宽表：指六压力场景；中位 ε 个别不可行要**主动披露**。  
- 可选：点「当场三模式」（短时限）；强调完整 81 点网格仍用 CLI。  
- 口播锚点：`STATUS.md` 里 calib 三模式 OPTIMAL 表。

### 4. 对照（约 1.5min）· H3 / S3

- **单次对照**：Fair 同池（同 stay_ids）+ 同资源（隔离/呼吸机/分区）。  
  - 诚实结论：小池上三法 assigned 常打平 → **不包装成 RL 更优**。  
- **多 episode 深化**：同池抽样重复；看均值表；仍标 offline。  
- 无 `artifacts/ppo_icu` 时：说明权重不入 Git，现场可跳过按钮、只讲方法。

### 5. 验收（约 40s）

- Layer1 行数门禁 ≈ 94458 stays / SOFA。  
- 收尾三句：默认 CP-SAT · MOO 可解释 · PPO 离线对照、不宣称 online。

## 一键启动

```powershell
cd "C:\Users\lenovo\Desktop\decision shcedule\icu-scheduling-agent"
.\scripts\run_console.ps1
# http://localhost:8502
```

可选 CLI（演示前预热报告，不入 Git）：

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m application.run_moo_phase4 --split eval --max-time 20
# 有 PPO zip 时：
# .\.venv\Scripts\python.exe -m application.compare_policies
# .\.venv\Scripts\python.exe -m application.evaluate_ppo_benchmark --episodes 3
```

## 超时砍刀（压到 3 分钟）

只讲：**运行 KPI → 多目标三种机理 → 对照 fair 同池 + 禁 online**。
