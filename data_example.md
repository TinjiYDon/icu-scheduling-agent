# 数据样例与探查记录

> 数据源：PostgreSQL 16（Docker 容器 `icu_scheduling_pg16`，`localhost:5434`）
> 探查日期：2026-10-22
> 规模：`staging.icustays` 94,458 条 ICU stay

---

## 1. 表结构

| 表 | 字段 |
|----|------|
| `staging.icustays` | `stay_id, subject_id, hadm_id, first_careunit, last_careunit, intime, outtime, los_hours` |
| `feat.sofa_timeseries` | `stay_id, hour_index, sofa_total` |
| `feat.patient_priority` | `stay_id, priority_weight` |
| `sched.assignments` | `id, run_id, stay_id, bed_id, created_at` |

---

## 2. 样例数据

### 2.1 `staging.icustays`（按 stay_id 升序取 5 条）

| stay_id | subject_id | hadm_id | first_careunit | intime | outtime | los_hours |
|---------|------------|---------|----------------|--------|---------|-----------|
| 30000153 | 12466550 | 23998182 | Trauma SICU (TSICU) | 2174-09-29 04:09 | 2174-09-30 19:26 | 1.64 |
| 30000213 | 13180007 | 27543152 | Medical Intensive Care Unit (MICU) | 2162-06-20 21:38 | 2162-06-22 12:52 | 1.64 |
| 30000484 | 18421337 | 22413411 | Medical Intensive Care Unit (MICU) | 2136-01-14 09:23 | 2136-01-16 20:53 | 2.48 |
| 30000646 | 12207593 | 22795209 | Coronary Care Unit (CCU) | 2194-04-28 17:39 | 2194-05-03 10:23 | 4.70 |
| 30000831 | 15726459 | 22744101 | Coronary Care Unit (CCU) | 2140-04-17 13:26 | 2140-04-20 06:21 | 2.71 |

> 时间戳为 MIMIC 去标识化后的偏移年份。

### 2.2 `feat.sofa_timeseries`（同上 5 名患者）

| stay_id | hour_index | sofa_total | first_careunit |
|---------|------------|------------|----------------|
| 30000153 | 0 | 4.0 | Trauma SICU (TSICU) |
| 30000213 | 0 | 7.0 | MICU |
| 30000484 | 0 | 5.0 | MICU |
| 30000646 | 0 | 4.0 | CCU |
| 30000831 | 0 | 6.0 | CCU |

### 2.3 `feat.patient_priority`

| stay_id | priority_weight | sofa_total |
|---------|-----------------|------------|
| 30000153 | 1.4 | 4.0 |
| 30000213 | 1.7 | 7.0 |
| 30000484 | 1.5 | 5.0 |
| 30000646 | 1.4 | 4.0 |
| 30000831 | 1.6 | 6.0 |

### 2.4 `sched.assignments`（最近 5 条）

| id | run_id | stay_id | bed_id | created_at |
|----|--------|---------|--------|------------|
| 1284 | p0_5e2ce0cb | 31496854 | 12 | 2026-09-14 13:46:14 |
| 1283 | p0_5e2ce0cb | 39658632 | 9 | 2026-09-14 13:46:14 |
| 1282 | p0_5e2ce0cb | 38905099 | 10 | 2026-09-14 13:46:14 |
| 1281 | p0_5e2ce0cb | 37189968 | 18 | 2026-09-14 13:46:14 |
| 1280 | p0_5e2ce0cb | 35923041 | 19 | 2026-09-14 13:46:14 |

### 2.5 模型取数顺序下的前 10 名候选

| stay_id | first_careunit | sofa | priority | iso 关键词命中 |
|---------|----------------|------|----------|----------------|
| 30064481 | MICU/SICU | 12.0 | 2.20 | 1 |
| 30075468 | SICU | 12.0 | 2.20 | 1 |
| 30230470 | MICU/SICU | 12.0 | 2.20 | 1 |
| 30254621 | MICU | 12.0 | 2.20 | 1 |
| 30316992 | MICU/SICU | 12.0 | 2.20 | 1 |
| 30508143 | SICU | 12.0 | 2.20 | 1 |
| 30545464 | SICU | 12.0 | 2.20 | 1 |
| 30676468 | SICU | 12.0 | 2.20 | 1 |
| 30772145 | SICU | 12.0 | 2.20 | 1 |
| 30879445 | MICU | 12.0 | 2.20 | 1 |

> 前 200 名中，关键词判定为隔离需求的有 **191 人**。

---

## 3. 分布统计

### 3.1 SOFA（`hour_index = 0`）

| sofa_total | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|------------|---|---|---|---|---|---|---|---|---|----|----|----|----|
| 人数 | 3,207 | 212 | 98 | 1,142 | 49,766 | 18,006 | 9,934 | 5,176 | 5,008 | 1,075 | 525 | 194 | 115 |

- 均值 4.735，标准差 1.629，范围 0–12。
- 4 分与 5 分合计 67,772 人，占 71.7%。

### 3.2 病区分布（前 8）

| first_careunit | 人数 |
|----------------|------|
| Medical Intensive Care Unit (MICU) | 20,703 |
| Medical/Surgical Intensive Care Unit (MICU/SICU) | 15,449 |
| Cardiac Vascular Intensive Care Unit (CVICU) | 14,771 |
| Surgical Intensive Care Unit (SICU) | 13,009 |
| Coronary Care Unit (CCU) | 10,775 |
| Trauma SICU (TSICU) | 10,474 |
| Neuro Intermediate | 5,776 |
| Neuro Surgical Intensive Care Unit (Neuro SICU) | 1,751 |

---

## 4. 关键特征

### 4.1 SOFA 是计算得到的，不是直接读取的现成字段

计算逻辑位于 `domain/scoring/sofa.py`：

1. 从 `mimiciv_hosp.labevents` 取入 ICU 后 **24 小时窗口**内的化验值；
2. 仅使用三个器官系统：
   - 肌酐 creatinine（itemid 50912 / 52546）→ 肾；
   - 胆红素 bilirubin（itemid 50885）→ 肝；
   - 血小板 platelet（itemid 51265 / 51277 / 53157）→ 凝血；
3. 每个分量按阈值映射到 0–4 分，求和得到 0–12 分；
4. 写入 `feat.sofa_timeseries`，固定 `hour_index = 0`；
5. 同一循环内写入 `priority_weight = round(1 + sofa_total / 10, 4)`。

说明：

- 表名虽为 `sofa_timeseries`，实际**每名患者只有一条记录**，不是时间序列；
- 缺失化验值按 0 分处理，因此"0 分"同时代表"正常"与"无数据"，共 3,207 人；
- 呼吸、循环、中枢神经三个系统未纳入，评分上限为 12 而非临床常用的 24。

### 4.2 优先级与 SOFA 完全共线（旧版构造）

旧版对全部 94,458 条记录满足：

```
priority_weight = 1 + sofa_total / 10     （精确成立）
```

由此可得：

$$
f_1=\sum_i(1+s_i/10)x_{ib}=f_0+0.1\sum_i s_ix_{ib}
$$

$f_0$、$f_1$、$f_2$ 在数学上高度相关，不能视为三个独立目标。

> 2026-10-27 起默认改为 `priority.mode=composite`：
> $w_i=1+0.6\,s_i/12+0.4\,\tilde L_i$，$\tilde L_i$ 为住院时长（`los_hours`，实际单位为天）的经验分位数。
> `priority.mode=sofa_rule` 保留上述旧公式，仅作基线。

### 4.3 隔离标记基于病区名称

代码使用 `first_careunit` 关键词（`micu` / `sicu` / `cvicu` / `nsicu`）判定隔离需求：

- 全库命中约 76,000 人；
- 模型取数顺序下的前 200 名中命中 **191 人（95.5%）**；
- 配置中隔离床仅 4 张，因此单轮可分配人数上限约 13 人。

> 2026-10-27 起改为可配置：`isolation.mode` 支持 `none`（默认，无隔离需求，ISO 床按普通床处理）、`careunit_keyword`（上述旧逻辑，仅作对照）、`real`（读取 `feat.stay_flags`）。

### 4.4 其他字段问题

| 项 | 观察 | 说明 |
|----|------|------|
| `los_hours` | 样例 1.64、2.48、4.70 | 实际单位为**天**；已通过 `staging.icustays_v.elapsed_hours` 提供小时单位 |
| 呼吸机需求 | 无真实标签 | `vent.mode` 支持 `none` / `pseudo_random` / `proxy_rule` / `real`；代理规则（SOFA≥5 且 ICU 病区）覆盖 34.7%；假设任意床可接呼吸机 |
| 候选池 | `candidates.mode` 可配置 | 默认 `fixed_sample`（确定性抽样），旧行为为 `top_score` |
| 历史分配 | 75 个 run，平均 16.6 人/轮 | 与当前隔离逻辑下的理论上限 13 人不一致 |

---

## 5. 复现命令

```powershell
# 启动数据库容器
docker start icu_scheduling_pg16

# 连接（容器内）
docker exec -it icu_scheduling_pg16 psql -U postgres -d icu_scheduling

# 重新计算 SOFA（当前无 CLI 入口，需在脚本中调用）
$env:PYTHONPATH = (Get-Location)
python -c "from domain.scoring.sofa import compute_sofa_timeseries; print(compute_sofa_timeseries())"
```

> 注意：`compute_sofa_timeseries()` 会先 `TRUNCATE feat.sofa_timeseries`，并覆盖 `feat.patient_priority`。
