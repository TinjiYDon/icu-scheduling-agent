# PPO 模型交接说明（B → C）

> 2026-08-02 · 让队友 C 用训练好的 PPO 模型更新面板

## 一、zip 文件

| 项       | 内容                                                       |
| -------- | ---------------------------------------------------------- |
| 文件     | `artifacts/ppo_icu.zip`（约 281 KB）                       |
| 来源     | B 本地训练（200K 步 · 8.6 分钟）                           |
| 传递     | **不走 Git**（`artifacts/` 已 gitignore）→ 网盘/文件手动传 |
| 放置路径 | `d:\project\icu-scheduling-agent\artifacts\ppo_icu.zip`    |

> ⚠️ 必须放对路径，`run_ppo.py`/`evaluate_ppo.py` 默认读 `artifacts/ppo_icu`。

## 二、模型信息

| 项       | 值                                                                                     |
| -------- | -------------------------------------------------------------------------------------- |
| 算法     | MaskablePPO（MlpPolicy）· `sb3-contrib 2.9`                                            |
| 训练步数 | 200,000（收敛，训练奖励 68 → 74.6）                                                    |
| 配置     | `optimizer.yaml` → `ppo` 段（lr=3e-4 · gamma=0.99 · batch=64 · n_steps=256 · seed=42） |
| 数据     | 真实 SOFA（20260727 dump）训练池 200 患者 × 20 床                                      |
| 评估     | PPO 73.1 vs Greedy 73.6 vs CP-SAT 13/200（`reports/ppo_evaluation.json`）              |

## 三、面板接入状态

运行台（`presentation/ui/ops.py`）已支持 `CP-SAT / PPO` 策略切换：

- `CP-SAT`：继续走 `run_simulation_with_plan(n_steps=n_steps)`，保留滚动图、历史表和解释文本。
- `PPO`：走 `application/run_ppo.py` → `predict_assignments()`，展示分配结果、总奖励和 reward 分解。

命令行验证（不依赖面板）：

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m application.run_ppo       # PPO 推理
.\.venv\Scripts\python.exe -m application.evaluate_ppo  # PPO vs Greedy vs CP-SAT
.\.venv\Scripts\python.exe -m application.evaluate_ppo_benchmark --episodes 5
```

> 备注：`evaluate_ppo_benchmark` 会让 PPO / Greedy / CP-SAT 在同一批 `candidate_stay_ids` 上重复评估，适合做“深入对比”验收。

## 四、注意事项

- 模型在 **20260727 dump** 上训练；若数据库 dump 更新（20260802），先验证或重训
- 无 MIMIC online 轨迹时**不宣称** online RL 已上线（`PPO_SMOKE.md` 约定）
- zip **不入 Git**；面板接入的**代码**走 Git（本分支已含 `run_ppo.py`/`evaluate_ppo.py`）
- PPO 小环境评估 ≈ Greedy（隔离床瓶颈下），接入后建议标注为「研究演示」
