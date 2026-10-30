# ICU 调度项目交接 README

> 交接日期：2026-10-30
> 交付分支：`feat/rolling-safety-handoff`
> 基线：`main` 的 `34fe955`（PR #16 合并提交）

本分支集中修复滚动调度安全、方法对照口径、实验候选规模和测试隔离问题，并补齐真实数据复验。项目默认策略仍为 `cp_sat`，优先级来自仓内 SOFA / GBDT，不接入其他项目的 `risk_score`。

## 1. 接手先看什么

1. 本文件：运行步骤、交付范围与后续任务。
2. [本次详细修复与验证记录](docs/LOCAL_VALIDATION_20261030.md)：命令、结果和研究局限。
3. [项目状态](docs/STATUS.md)：当前结果及注明日期的历史实验。
4. [总目标与主线](docs/MASTER_NARRATIVE.md)：可审计、可对照、可滚动。
5. [轨迹协议 2.0](docs/TRAJECTORY_PROTOCOL.md)：旧消费者迁移时必读。

## 2. 本次交付

| 模块 | 变更 | 主要文件 |
|------|------|----------|
| 滚动调度 | 默认保留在院患者，禁止优化器代替出院；零周转率生效，患者守恒、事件计数与失败回退可审计 | `domain/rolling/engine.py` |
| CP-SAT | 增加 `retain_occupied` 与 `max_new_admissions`，统一科室错配目标与解释口径 | `domain/optimizer/cp_sat.py` |
| H6 对照 | 两策略复用相同初始分配；贪心也执行隔离与呼吸机约束，报告保留求解失败和约束指标 | `application/run_rolling_contrast.py`、`domain/ops/rolling_contrast.py` |
| PPO / 贪心 | 普通患者可用空闲隔离床；统一隔离患者科室错配豁免与高危落普通床的惩罚条件 | `domain/rl/env.py` |
| H5 / 方法对照 | 修复指定 40 人却被默认 20 人环境截断；候选规模传到环境构建入口 | `domain/rl/factory.py`、`application/run_pto_ablation.py`、`application/run_method_bakeoff.py` |
| GBDT | 补充 `scikit-learn` 依赖；仅导入 LightGBM 失败时选后备实现，训练错误正常暴露 | `pyproject.toml`、`domain/scoring/predict_priority.py` |
| 轨迹导出 | 明确关闭调度写库，校验文件名与步数；修正前后状态，提供实际约束检查与奖励代理说明 | `domain/rl/trajectory.py`、`application/export_trajectory.py` |
| 测试 / CI | 移除测试加载时的数据库连接；数据库测试显式开启，CI 执行完整无数据库测试 | `tests/conftest.py`、`tests/test_*.py`、`.github/workflows/ci.yml` |
| 文档 | 清理过期待办，区分历史数字、最终复验、仿真轨迹与真正的 offline RL | `docs/ROADMAP*.md`、`docs/BACKLOG.md`、`docs/STATUS.md` 等 |

### 必须注意的接口变化

- `run_rolling_simulation()` 默认 `retain_occupied=True`。只有研究旧行为时才显式设为 `False`；普通调度保持默认。
- `run_assignment()` 的 `retain_occupied` 默认为 `False`，供快照求解向后兼容；滚动引擎会显式启用留院约束。
- 轨迹版本升为 `2.0`：`state` 为转移前状态，`next_state` 为转移后状态。旧版读取“转移后 state”的逻辑应改为读取 `next_state`。
- `constraint_violation=null` 表示没有检查结果；不能视为通过。轨迹里的 `wait` 是空床数代理，不是等待时长，也不是 `priority_served` 或完整 PPO 奖励。
- 原 PPO zip 本次能够加载和评估；奖励与可行域修复后，应记录新实验版本，旧训练奖励不与新奖励直接比较。

## 3. 获取代码与安装

在已有仓库中先保存未提交工作，再执行：

```powershell
git fetch origin
git switch feat/rolling-safety-handoff
git log -1 --oneline
```

首次建立开发环境时，在仓库根目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
$env:PYTHONPATH = (Get-Location).Path
```

有现成虚拟环境时保留环境，更新项目依赖即可。Python 要求为 3.11+；本次 Windows 本地验收使用 Python 3.13.9，CI 配置使用 Python 3.12。

## 4. 测试与数据库准备

无需数据库即可运行完整普通测试：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

本机结果为 **217 passed / 6 skipped**。其中 4 项数据库集成测试默认跳过，2 项符号链接测试因 Windows 权限跳过，其他系统的计数可能不同。

真实数据实验需要本机 PostgreSQL 的 `icu_scheduling` 数据库；本次核对以下三表各 94,458 行：

- `staging.icustays`
- `feat.sofa_timeseries`
- `feat.patient_priority`

连接可通过本地 `configs/database.yaml` 或 `.env` / `DATABASE_URL` 配置。有效的 `database.yaml` URL 优先；只有该文件缺失或仍含 `CHANGE_ME` 时，才使用环境变量、`.env` 或默认连接。Docker 的映射端口可能为 5434，须与本机 DSN 一致。

有现成数据库时可运行三项只读集成测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cp_sat_quick.py tests/test_db.py --run-db -q
```

本次 **3 passed**。不要把该命令改为不加筛选的 `--run-db` 全量运行来做只读核验：`test_etl_smoke` 会运行 ETL 并写特征表，本次未执行它。

新机器需要恢复 dump 时先读 [DUMP_READY.md](docs/DUMP_READY.md)。`restore_layer1.ps1` 默认重建目标数据库，执行前核对目标和已有数据；已经有本次三表时无需恢复或重跑 ETL。

## 5. 复现实验与运行台

以下命令在仓库根目录执行。所列实验求解使用 `persist=False`，读取数据库并生成本地报告。

```powershell
# 需要线下交接的原 PPO 检查点 artifacts/ppo_icu.zip
.\.venv\Scripts\python.exe -m application.evaluate_ppo
.\.venv\Scripts\python.exe -m application.evaluate_ppo_benchmark --episodes 3

# 不需要 PPO 检查点
.\.venv\Scripts\python.exe -m application.run_method_bakeoff --candidate-patients 40 --max-time 20
.\.venv\Scripts\python.exe -m application.run_pto_ablation --candidate-patients 40 --max-time 20
.\.venv\Scripts\python.exe -m application.run_rolling_contrast --steps 8
.\.venv\Scripts\python.exe -m application.run_moo_phase4 --split eval --max-time 20
.\.venv\Scripts\python.exe -m application.run_moo_phase3 --split calib --levels 3 --max-time 15 --baseline-max-time 90
.\.venv\Scripts\python.exe -m application.export_trajectory --steps 4

# 启动运行台
.\scripts\run_console.ps1
```

本次验收摘要：

| 实验 | 最终实测 |
|------|----------|
| PPO 单轮 | 同池 20 人、同资源，PPO / Greedy / CP-SAT 各分配 5 人，均无约束违反 |
| PPO 3 episodes | 三策略平均分配数均为 5，平均高危未服务数均为 15，均无约束违反 |
| 40 人 bake-off / H5 | 候选确实为 40 人；SOFA-only vs 公式分配名单 Jaccard=0.1111，GBDT vs 公式=1.0 |
| H6 8 步 | 两策略最终均为 18 床，平均 SOFA 均为 10.0667、平均权重均为 2.0056；本设定打平 |
| 六资源压力场景 | WS / Lex / ε 共 18 次求解全部 OPTIMAL |
| Pareto / HV | 最终 27 网格、17 可行、3 非支配，HV=0.052130；本次 balance payoff 轴退化，不能默认网格固定为 81 点 |
| 轨迹 2.0 | 4 transitions；真实输出已验证状态连续、人数守恒及约束检查无违反 |

上述是特定数据、配置与版本下的结果。历史 `81/54/4/HV=0.038794` 与本次结果分版本保存，不能跨 payoff 范围直接比较 HV。

## 6. 需要线下交接的文件

以下文件受 `.gitignore` 保护，不随本分支上传：

| 文件或目录 | 接手方式 |
|------------|----------|
| scheduling 数据 dump | 从项目已有线下渠道获取，按 `DUMP_READY.md` 核对恢复目标 |
| `artifacts/ppo_icu.zip` | 原模型单独交接；缺少时先跳过 PPO 两个命令，其余实验可运行 |
| `reports/` | 按上节命令重新生成；新 clone 缺少报告时运行台会显示 missing，属于预期状态 |
| `artifacts/trajectories/` | 运行 `export_trajectory` 重新生成 |
| `.env`、本地数据库与数据源配置、`.venv/` | 每台机器自行配置，不将密码提交到 Git |

本次复验的 PPO zip SHA-256：

```text
0bdb849a9e19f9bd3106c01db92d44d0c16a3d27aea3dd821ec1ce058d836c0d
```

## 7. 下一步任务

| 建议顺序 | 工作 | 验收要求 |
|----------|------|----------|
| 1 | 消除事后信息泄漏 | `los_hours` 来自完整住院记录；改用决策时刻可获取的特征，明确训练标签与时点 |
| 2 | 冻结独立验证协议 | 保存训练 / 校准 / 评价患者清单，证明互斥，开展多种子、多资源布局实验 |
| 3 | 改进 Pareto 覆盖 | 复核 payoff 取值与退化轴；记录范围、参考点和归一化，验证可重复性 |
| 4 | 真实纵向调度状态 | 接入按时间排序的入出转、SOFA 与设备事件，检验等待时长和需求规则 |
| 5 | 偏好条件 / 固定数据 offline RL | 明确逐患者 observation、action、reward、约束和缺失值协议，再实现 CQL/IQL 等；保留 CP-SAT 可行性校验 |

当前 PPO 是与仿真环境交互训练及离线评估，导出的聚合轨迹尚不是可直接训练的 offline RL 数据集；`hybrid` 为预留功能。后续汇报应继续说明这一边界，避免把工程复验等同于临床效果或学术领先。
