# 轨迹协议 · ICU Scheduling RL（S2-TRAJ）

> 协议 `2.0`：修正转移方向，披露约束检查来源和奖励代理语义。
> 本包不能单独支撑 online MIMIC-PPO、床旁临床 RL 或 RL 训练奖励已对齐的结论。

## 目的与边界

导出滚动 CP-SAT 仿真的离线审计包，用于检查周转、状态变化和工程 smoke。
这是仿真快照与聚合动作，不是真实 MIMIC 床旁事件日志，也不是已经适配 MaskablePPO 的训练数据集。
不把这些摘要宣称为完整的 RL observation、可重放的逐患者 action 或完整的 Markov 状态。

## 导出

在仓库根目录执行：

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m application.export_trajectory --steps 12
.\.venv\Scripts\python.exe -m application.export_trajectory --steps 2 --name audit.json
```

- 导出明确调用 `run_rolling_simulation(n_steps=..., persist=False)`，关闭调度结果的 `sched` 持久化；仿真仍读取数据库。运行 CLI 并不等于无数据库测试。
- `n_steps` / `--steps` 必须为 `0..10000` 的整数；Python API 不接受布尔值、字符串、浮点数或隐式截断。`0` 仍运行初始分配、导出摘要，但没有 transition。
- `out_name` / `--name` 只接受合法的 JSON basename，例如 `audit.json`，不能包含目录、盘符、路径分隔符、Windows 保留设备名、非法字符或首尾空白。扩展名不区分大小写。API 的 `None` 表示自动命名；空字符串无效。
- 输出位于 `artifacts/trajectories/`：命名文件及同内容的 `rolling_traj_latest.json`，均不入 Git。已存在的输出文件链接若指向目录之外，会拒绝导出。无效参数在配置读取、仿真和文件创建之前拒绝。

## Schema（protocol_version = 2.0）

包保留 `created_at`、`source`、`n_beds`、`step_hours`、`n_steps`、`summary`、`transitions`、`notes` 等旧键，并新增 `reward_semantics`。

| 字段 | 含义 |
|------|------|
| `t` / `dt_hours` | 转移结束时的历史步号 / 时间步长 |
| `state` | `history[i-1]`：转移前快照 |
| `next_state` | `history[i]`：转移后快照 |
| `state.occupied` / `free_beds` | 转移前占床数 / `max(n_beds - occupied, 0)`；`next_state` 同构 |
| `state.avg_sofa` / `avg_weight` | 对应快照的占用病情 / 优先级摘要；`next_state` 同构 |
| `state.assignments` / `next_state.assignments` | 引擎若提供则原样复制，含 `stay_id`、`bed_id` 等字段；未提供则省略，不伪造分配 |
| `state.constraint_violation` / `next_state.constraint_violation` | 对应快照的引擎检查结果：`true` / `false` / `null`；包含初始状态的结果 |
| `action.admitted` / `discharged` | 结束快照记录的本步计数，保留旧键 |
| `action.policy` | 保留旧标签 `rolling_cp_sat_fill`，不是可重放的逐患者策略动作 |
| `action.admitted_stay_ids` / `discharged_stay_ids` / `returned_to_queue_stay_ids` | 引擎若提供则透传本步事件 IDs；返回队列与出院含义不同，不从占床数差值推断 |
| `action.solver_status` | 引擎若提供则透传；求解器状态本身不能替代实际约束校验 |
| `reward_components` | 转移后状态计算的未加权代理量，见下节 |
| `constraint_violation` | 与 `next_state.constraint_violation` 一致的旧兼容键 |
| `constraint_check_status` | 有明确布尔结果时为 `checked`，否则为 `unknown` |
| `prev_occupied` | 保留的旧键，等于 `state.occupied` |

### 版本兼容

`1.0` 的 `state` 实际使用转移后快照，且把未检查的 `constraint_violation` 固定为 `false`。
`2.0` 保留旧键，但修正这些语义，因此明确提升主版本，不能静默按 `1.0` 消费。
读取 `2.0` 时，需要旧版转移后摘要的消费者应使用 `next_state`；约束消费者必须接受 JSON `null`，不能把未知当成通过。
历史 `1.0` 文件不会自动重写，其中的固定 `false` 不应作为校验通过证据。

历史中有初始快照和 N 个后续快照时产生 N 个 transition，初始分配不另算一次转移。
只有空历史或单个快照时，`transitions=[]`。

### 约束审计

导出器不自行复算床位布局、隔离、呼吸机和患者/床位唯一性约束；这些检查由滚动引擎负责。
仅当快照明确提供布尔类型的 `constraint_violation` 时，导出器保留该结果。
缺失、`None` 或非布尔值一律导出 `null` / `unknown`，不会用求解器状态、占床率或空列表推定通过。
兼容没有新字段的历史：事件 IDs、assignments 和 solver_status 缺失时省略；计数字段仍保留。

### 奖励语义与 RL 边界

| 分量 | 实际计算 | 限制 |
|------|----------|------|
| `occupancy` | `next_state.occupied / max(n_beds, 1)` | 未加权利用率代理 |
| `wait` | `float(next_state.free_beds)` | 保留的旧键，是 `wait_proxy` 的别名 |
| `wait_proxy` | `float(next_state.free_beds)` | 空床数代理，不是等待时长或 `priority_served` |

这些分量没有应用 `optimizer.yaml` 的 `lambda.*` 或 `rl.reward_weights`，也不等同于 `ICUEnv` / PPO 的奖励。
`wait` 与优化器的优先级服务收益、训练中的等待惩罚/优先级奖励在含义、符号、尺度和动作粒度上不能直接等同。
包内 `reward_semantics` 与 `notes` 明示此边界；不能用字段同名作为 RL 训练奖励已经对齐的证据。
生产默认仍为 `cp_sat`；后续若用作训练数据，需另行定义 observation、action、奖励和约束缺失值处理并验证。

## 无数据库回归验证

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_trajectory_export.py -q
```

测试使用明确标注的合成 history、替代仿真函数和临时输出目录，并阻断真实仿真及数据库入口。
覆盖真实导出函数生成的 JSON 与 latest 副本、`persist=False`、参数/路径拒绝、转移方向与连续性、
事件 IDs / assignments / solver_status 透传、约束三态、奖励披露、零步边界和 CLI 错误处理。
文件链接越界测试在系统不支持创建符号链接时跳过。
上述单测不访问数据库。2026-10-30 另在本地 MIMIC 特征库真跑 `--steps 4`，导出协议 `2.0` 的 4 个 transition，并复核状态连续、逐步人数守恒及引擎约束检查均为无违反。该结果仍是基于真实特征的仿真审计包，不是真实床旁事件轨迹。
