# 六分量 SOFA 与因果时间标签

本次对应 `origin/main-archive:MULTIOBJECTIVE_TASKS.md` 的 D3。新实现位于 `domain/scoring/sofa_full.py`；旧 `sofa.py` 的三分量首日数据库流程保留作为历史基线。本次小样本入口使用六分量 JSON，不把历史 dump 的三分量分数称作完整 SOFA。

## 数据与抽样契约

`python -m application.prepare_sofa_sample` 从本地 `mimic-iv-3.1.zip` 读取 `icustays`，按 `stay_id` 排序后用 Python `random.Random(seed).sample` 抽取 50 个 stay。默认先限定真实 ICU 时长至少 48h，以支撑 warmup=24h 后的 24h 验证；这是**长住院样本选择偏差**，不能据此估计总体表现。真实出科时间仅用于研究样本筛选、限制评分记录范围，不作为优化器输入或出院预测。

事件抽取只保留所选 stay、入科后 0–48h 的指定项目。lab 通过 `subject_id`、非空时的 `hadm_id`、患者自身 ICU 起止时间关联；血气必须有相同 `specimen_id`。其余表直接使用 `stay_id`。`labevents/chartevents/inputevents/outputevents` 逐块扫描，不完整解压；通气判据使用 chart 中设备/模式，不依赖 `procedureevents` 的事后持续区间。文件读遍不等于全库计算 SOFA。

缓存 `artifacts/sofa_sample/manifest.json` 保存 archive 路径、大小、mtime、各 gzip 成员 CRC、抽样 seed、项目清单和 stay 清单；各表保存独立 JSONL，临时 `.part` 完成后原子改名。读取 gzip/ZIP 至 EOF 时由库校验对应完整性，CRC记录本身不是未读数据的校验结果。每完成一张表原子更新 manifest，续跑保留已完成表的扫描统计。改抽样参数、archive 或保留项目时必须另设缓存目录，不会静默复用不匹配缓存。缓存包含受限患者记录，目录已被 Git 忽略。

## 两种时间

患者局部决策时刻为 `t_i = intime_i + hour_index`。默认 `hour_index=0,2,...,48`，评分窗口是 `intime_i ≤ charttime ≤ t_i` 与 `(t_i−24h,t_i]` 的交集。恰好落在 `t_i−24h` 的记录排除；入科不足 24h 标记 `partial_window=true`。`window_start` 是有效窗口的下界，`window_end` 是决策时刻。

同一记录必须同时满足**观测时间不晚于决策时刻、storetime 不晚于决策时刻**。缺少 storetime 的记录不回退到 charttime，而是排除并输出 `missing_storetime_excluded`。已采样但尚未入库的 lab 不能出现在早期决策里。input 的事件时刻取 starttime，不使用将来的 endtime 或最终持续时长。PaO₂ 的 FiO₂ 配对以及 GCS 前条补值均只向过去查找。

相对入科时间不等于不同患者共享的真实日历时间；用于调度的跨患者构造时间轴另见滚动说明。2h 是**重新决策步长**，24h 是**评分回顾窗**，本实现没有新增未来预测窗口。

## 评分数据口径

每个分量输出 0–4 或 null。对已观察到的有效资料取窗口内最差评分，六分量之和范围 0–24。缺分量暂按 0 贡献计算 `sofa_total`，同时必须保留 `missing_components`，不能把缺失当作已测正常。`n_observed_components` 仅表示至少有一种可评分输入，并不证明该系统的所有临床输入完整。

| 分量 | 项目与单位 | 评分 |
|---|---|---|
| 呼吸 | 动脉标本 52033=`ART.`，PaO₂ 50821 mmHg；同标本 FiO₂ 50816 优先，否则取血气前 4h 内最近的 223835 | P/F <400 为1、<300 为2；有创通气且 <200 为3、<100 为4 |
| 凝血 | 血小板 51265/53189，K/uL、10³/uL 或10⁹/L | <150/100/50/20 分别1/2/3/4 |
| 肝 | 总胆红素 50885/53089，mg/dL | ≥1.2/2/6/12 分别1/2/3/4 |
| 循环 | MAP 220052/220181/225312，mmHg；dopamine 221662、dobutamine 221653、epinephrine 221289、norepinephrine 221906 | MAP<70 为1；dopamine>0且≤5 或 dobutamine>0 为2；dopamine>5且≤15 或 epi/norepi>0且≤0.1 为3；dopamine>15 或 epi/norepi>0.1 为4 |
| 神经 | GCS verbal 223900、motor 223901、eyes 220739 | GCS 13–14/10–12/6–9/<6 分别1/2/3/4 |
| 肾 | 肌酐 50912/52546，mg/dL；有效24h尿量 mL | 肌酐≥1.2/2/3.5/5 分别1/2/3/4；尿量<500 为3、<200 为4，取二者较高分 |

不支持的 lab、PaO₂、药物单位会排除并记 quality flag；不把旧代码中其他液体/检验项目错误地混成血小板。FiO₂ 的 0.2–1 转为比例，20–100 除以100，其他数值排除。无动脉标本或无过去 FiO₂ 时呼吸分量缺失，不能使用静脉氧分压代替。

通气证据采用血气前 4h 内最近设备/模式时间；`Endotracheal tube` 或官方有创模式名单作为有创支持，较晚的设备记录可覆盖较早模式。查不到支持时保守按无支持档评分，并标记 `respiratory_support_unknown_scored_without_support`；这可能低估呼吸评分。没有从 FiO₂ 高值或病区名称推断有创支持。

药物只使用截至 t 已入库、起始时间落在回顾窗内的记录速率，跳过 `Rewritten`。速率统一为 mcg/kg/min：直接接受 mcg/kg/min、ug/kg/min；mg/kg/min乘1000，norepinephrine的已知 weight=1异常按官方例外；mcg/min 按该条记录 patientweight 换算，其他单位排除。**没有通过未来 endtime 计算持续输注，也未把24h以前起始的药物自动延续到当前**，因此该小样本因果版本可能漏记长输注，不能称为官方完整药物时间区间复刻。

GCS 同时刻三项合并；最多向前取紧邻的一组且间隔<6h补值，其他缺项按正常分补并标记 `gcs_partial_components_default_normal`。`No Response-ETT` 不按昏迷计分，而依官方约定置 GCS=15并标记 `gcs_ett_default_15`；从 ETT 恢复的记录不携带先前低 motor/eyes。没有独立重建镇静前神经检查，不能把该分数解释为已排除镇静混杂。

尿量项目为226559/226560/226561/226584/226563/226564/226565/226567/226557/226558/227488/227489；227488灌注入量作负值扣除，其他负值排除。禁止把无记录当零尿量。为防短窗口误判，只有入科≥24h、有至少两条记录、首条距左端≤2h、末条距右端≤2h、相邻记录间隔≤6h且净量非负时采用24h总量，否则记 `urine_24h_insufficient_documented_coverage`，仍可凭肌酐评分。该规则是**文档覆盖代理**，不是导尿连续性证明；不对短观测窗线性外推。

## 与官方 SQL 的差异与来源

阈值和项目参考 MIT-LCP 的 [SOFA](https://github.com/MIT-LCP/mimic-code/blob/main/mimic-iv/concepts/score/sofa.sql)、[blood gas](https://github.com/MIT-LCP/mimic-code/blob/main/mimic-iv/concepts/measurement/bg.sql)、[GCS](https://github.com/MIT-LCP/mimic-code/blob/main/mimic-iv/concepts/measurement/gcs.sql)、[urine output](https://github.com/MIT-LCP/mimic-code/blob/main/mimic-iv/concepts/measurement/urine_output.sql)、[vitals](https://github.com/MIT-LCP/mimic-code/blob/main/mimic-iv/concepts/measurement/vitalsign.sql)、[ventilation](https://github.com/MIT-LCP/mimic-code/blob/main/mimic-iv/concepts/treatment/ventilation.sql)、[norepinephrine](https://github.com/MIT-LCP/mimic-code/blob/main/mimic-iv/concepts/medication/norepinephrine.sql)（核对日期2026-11-04）。item label另核对本地3.1字典。

官方为回顾性小时派生表、每分量再取24h最大值；本实现按2h决策点直接聚合过去24h，额外限制 storetime，尿量只计算当前24h窗，不再取“过去24h每小时24h尿量评分的最大值”（后者有效回顾可能延伸48h）。未复刻官方用未来相邻通气记录推断持续区间；未使用其尿量22–30h覆盖归一化。上述差异以避免未来信息、显式缺失及小样本可审计为目的，需要在论文方法中声明。不能据此称为经临床验证或与官方 SQL 数值完全相同。

## 运行、输出与验收

在仓库根目录：

```powershell
.\.venv\Scripts\python.exe -m application.prepare_sofa_sample --zip ..\mimic-iv-3.1.zip --size 50 --seed 42 --min-stay-hours 48 --hours 48 --extract-only
.\.venv\Scripts\python.exe -m application.prepare_sofa_sample --score-only
.\.venv\Scripts\python.exe -m pytest tests/test_sofa_full.py tests/test_mimic_sample.py -q --basetemp artifacts/test_sofa_temp
```

默认输出 `artifacts/sofa_sample/sofa_sample.json`：

- `stays`：选中患者标识及原始 stay 元数据。
- `scores`：stay_id、hour_index、window_start/end、partial_window、components、sofa_total、missing_components、n_observed_components、quality_flags、inputs、evidence、priority_weight。
- `evidence`：每个归一化输入的原始项目、时点、入库时间；P/F额外保留配对FiO₂及支持记录。GCS保留观测/补值项。
- `coverage`：行数、各分量可评分数量、24h六分量非缺失数量及quality flag计数；用于检查数据完整性，不是结果分析。
- `config`：archive身份、抽样参数、时间轴、缺失总分规则；优先级沿用旧式 `1+sofa_total/10`，只作为当前SOFA基线，不引入新预测模型、不使用真实最终LOS。

测试覆盖阈值、未来采样/入库泄漏、时间窗左边界、动脉标本和FiO₂配对、GCS-ETT、药物单位、短窗尿量、缺storetime、抽样复现、缓存错配及ZIP→评分小例。真实缺失不能通过调参强行消除，覆盖清单须随数据交接。
