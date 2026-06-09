# 项目一：ICU 医疗资源动态调度智能体

> 目录：`icu-scheduling/` · 仓库：`icu-scheduling-agent`  
> 数据库：`icu_scheduling`（PostgreSQL 16，独立实例）

---

## 1. 定位与边界

**做什么**

- 基于临床评分与科室状态，用 **OR-Tools CP-SAT + PPO** 求解与学习型调度策略。  
- 滚动时域动态更新；Streamlit 展示调度方案与解释。

**不做什么**

- 不调用项目二 API，不读 `icu_decision` 库。

**输入 / 输出**

| 方向 | 内容 |
|------|------|
| 输入 | SOFA 等评分、床位/设备占用、等待队列、约束配置 |
| 输出 | 分配方案、转出顺序、目标函数分解说明、仿真指标 |

---

## 2. 领域架构（四层业务 + 五层代码）

### 2.1 业务四层（自底向上）

```
临床评分层 ──► 系统状态层 ──► 调度优化层 ──► 滚动执行层
   SOFA           床位/队列/设备    CP-SAT + PPO      1–2h 循环
```

| 层 | 职责 | 依赖 |
|----|------|------|
| ① 临床评分 | 从 vitals/labs 算 SOFA、优先级权重 | L2 `feat.sofa_*` |
| ② 系统状态 | 组装全局观测向量 | ① + L2 `sim.state_*` |
| ③ 调度优化 | 建模、求解、输出方案 | ② + `configs/optimizer.yaml` |
| ④ 滚动执行 | 推进一步时间、触发重算 | ③ |

### 2.2 代码五层与调用关系

```
streamlit_app  (L5)
      │ 调用
application/   (L4)  run_simulation · run_roll_step · run_replay
      │ 调用
domain/        (L3)  scoring · state · optimizer · rolling · simulation
      │ 调用
data_access/   (L2)  MimicRepository · FeatureRepository · SchedRepository
      │ 调用
infra/         (L1)  db session · config · logging
```

**禁止**：`dashboard/` 直接 `import optimizer.model` 内 SQL；必须经 L4 用例函数。

---

## 3. 技术栈与工具职责

| 工具 | 职责 | 不使用于 |
|------|------|----------|
| **PostgreSQL 16** | 持久化 raw/feat/sim/sched | — |
| **SQLAlchemy + psycopg** | 连接、事务、Repository | 业务规则 |
| **Polars** | 从 PG 拉取后的聚合、矩阵运算 | 替代 PG 做主库 |
| **OR-Tools CP-SAT** | 整数规划求解 | 数据存储 |
| **Streamlit** | 演示与参数面板 | 核心算法 |
| **pytest** | L2/L3 单测 | — |

---

## 4. 目录结构

```
icu-scheduling/
├── PLAN.md
├── configs/
│   ├── database.yaml      # PG 连接、database=icu_scheduling
│   ├── data.yaml          # source: mock | mimic
│   ├── optimizer.yaml     # λ、床位数、滚动窗口
│   └── sofa_itemids.yaml  # chartevents itemid 映射
├── infra/
│   ├── config.py
│   ├── db.py              # Engine、Session
│   └── logging.py
├── data_access/
│   ├── mimic_repo.py      # 只读 mimic_iv 或 raw.*
│   ├── feature_repo.py    # feat.* 读写
│   └── sched_repo.py      # sched.* / sim.*
├── domain/
│   ├── scoring/           # SOFA、priority
│   ├── state/             # 状态向量构建
│   ├── optimizer/         # CP-SAT 模型
│   ├── rolling/           # 滚动引擎
│   └── simulation/        # 历史回放
├── application/
│   ├── etl_pipeline.py
│   ├── simulate.py
│   └── roll_step.py
├── presentation/
│   └── streamlit_app.py
├── migrations/            # Alembic
├── tests/
└── reports/
```

---

## 5. 核心逻辑与数据流

### 5.1 ETL 管线

```
mimic_iv.* (或 raw.*)
    │  SQL 联表：icustays + transfers + chartevents + labevents
    ▼
staging.*  ──Polars 清洗──►  feat.sofa_timeseries
                          feat.bed_occupancy
                          feat.patient_priority
```

**触发**：`application/etl_pipeline.py::run_etl(config)`  
**写入**：L2 `FeatureRepository.bulk_upsert()`

### 5.2 单次调度求解

```
feat.patient_priority + sim.current_state
    │  domain/state/build_observation()
    ▼
domain/optimizer/build_model(obs, constraints)
    │  OR-Tools Solve()
    ▼
sched.assignments  +  解释 dict（各目标分项）
```

**触发**：`application/roll_step.py::execute_one_step()`  
**读**：L2 `SchedRepository.get_state()`  
**写**：L2 `SchedRepository.save_assignment()`

### 5.3 仿真回放

```
feat.* + transfers 历史
    │  domain/simulation/replay.py
    ▼
时间步循环 → 每步调用 roll_step
    ▼
reports/metrics.json + sim.run_log 表
```

---

## 6. 优化模型（MVP 范围）

### 6.1 决策变量

| 变量 | 含义 |
|------|------|
| `x(i,b)` | 患者 i → 床位 b |
| `y(i,t)` | 患者 i 在 t 转出 |
| `z(i,e)` | 患者 i → 设备 e |

### 6.2 目标与约束

```
min L = λ₁·f₁ + λ₂·f₂ + λ₃·f₃
```

- f₁：高风险加权等待（λ₁ 最大）  
- f₂：床位超负荷  
- f₃：资源均衡  

硬约束：床位数、分区、设备上限、一人一机、优先级、转科窗口（简化）。

### 6.3 可解释输出（MVP）

不依赖 SHAP；由 `domain/optimizer/explain.py` 输出：

- 每位患者被选中的 **优先级贡献**  
- 各 **硬约束** 绑定情况  
- **目标分项** 数值  

---

## 7. 配置自洽

| 文件 | 消费者 | 关键字段 |
|------|--------|----------|
| `database.yaml` | L1 `db.py` | `dsn`, `pool_size` |
| `data.yaml` | L4 `etl_pipeline` | `source`, `mimic_dsn` |
| `optimizer.yaml` | L3 `optimizer` | `lambda_*`, `n_beds`, `horizon_hours` |
| `sofa_itemids.yaml` | L3 `scoring` | itemid 列表 |

所有 magic number 进配置，L3 通过 `infra.config.load()` 读取。

---

## 8. 模块依赖顺序（实施时按此顺序打通）

```
1. infra + migrations          → PG 表结构就绪
2. data_access + mock 数据     → L2 读写通
3. domain/scoring              → SOFA 可算
4. domain/state + optimizer    → 单次求解通
5. domain/rolling + simulation → 多步仿真通
6. application 编排            → 命令行可跑全流程
7. presentation/streamlit      → UI 联调
8. ETL 切换 mimic 源           → 真实数据替换 mock
```

上一步未冒烟通过，不进入下一步；**不设固定日期**。

---

## 9. 扩展 backlog

| 项 | 接入点 |
|----|--------|
| PPO 强化学习 | 新增 `domain/rl/`，L4 可选策略 `policy=cp_sat|ppo` |
| SHAP 调度解释 | `domain/optimizer/explain_shap.py` |
| 完整 APACHE II | 扩展 `domain/scoring/apache.py` |
| eICU 验证 | 新 ETL 源 + 独立 `raw_eicu` schema |

---

