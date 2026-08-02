# λ 权重调优说明

## 目的

λ 控制 CP-SAT 在患者优先级、超负荷、区域均衡和科室匹配之间的取舍。配置可运行不等于参数已经调优；只有固定数据和场景上的实验结果才能形成推荐值。

四个原始目标会先按各自理论上界缩放到共同整数尺度，再乘 λ。求解结果的 `objective_scaling` 会返回本次上界和实际整数系数，避免优先级的 x1000 存储单位掩盖其他目标。

## 执行

快速敏感性实验（默认 calib 子集，调参不碰 eval）：

```powershell
python scripts/tune_lambda.py --quick --split calib
```

完整 256 组合实验：

```powershell
python scripts/tune_lambda.py --split calib
```

在 eval 子集上做最终评估（只评估，不回写调参）：

```powershell
python scripts/tune_lambda.py --quick --split eval
```

输出文件：

- `reports/lambda_tuning.csv`：全部实验。
- `reports/lambda_tuning_pareto.csv`：非支配解。
- `reports/lambda_tuning_recommended.json`：按公开排序规则选择的建议组合。

## 实验记录（2026-08-01 · quick 16 组 · calib 子集）

> 数据：真实 SOFA dump（94,458 stays）· 全部 OPTIMAL · 每次求解 <0.1s

| 观察 | 结果 |
|------|------|
| `wait` 为主导旋钮 | λ=0.1→2.0 时分配数 4→10 |
| `overload` 敏感 | 0.5→1.0 时分配数下降（更保守）|
| 瓶颈 | 所有组合隔离床 4/4 绑定（`isolation_utilization=1.0`），高危候选等待 130/140 |

**推荐组合（候选值，未写回）**：

```yaml
lambda:
  wait: 2.0
  overload: 0.5
  balance: 0.1
  zone_mismatch: 0.5
```

> ⚠️ 推荐值仅是 quick 敏感性结果，与当前配置（wait=10, overload=1）差异较大。
> 正式写回 `configs/optimizer.yaml` 前需：完整 256 组合 + 队友确认 6 场景 + eval 验证。

## 完整 256 组合实验（2026-08-02 · calib 子集）

> 搜索空间：4 个 λ 各取 {0.1, 0.5, 1.0, 2.0} = 256 组 · 全部 OPTIMAL · Pareto 前沿 9 个解

**最终推荐（Pareto 规则）**：

```yaml
lambda:
  wait: 0.5
  overload: 0.1
  balance: 0.1
  zone_mismatch: 0.1
```
→ 分配 10/140 · 优先级 21.6 · 科室匹配 0.80 · 求解 0.08s

| 关键 trade-off | 结论 |
|------|------|
| 分配上限 = 10 | 隔离床 4 + 可用非隔离床 6，瓶颈限制 |
| wait 主导分配数 | wait<0.5 只分 7 床；≥0.5 可达 10 |
| overload 太高少分床 | =1.0 时只分 4-9 床 |
| 所有解隔离床全满 | high_risk_waiting=130 → 真正的杠杆是资源，不是 λ |

> ⚠️ **未写回 `optimizer.yaml`**：推荐值需队友确认（6 场景验证）后在 eval 上复核。
> 备注：与 quick 推荐（wait=2.0）不同，完整网格在 balance/zone 维度补齐后权衡出 wait=0.5。

## 选择规则

程序不比较不同 λ 下不可比的求解器总目标值，而是比较原始业务指标。推荐顺序为：高风险患者分配率、科室匹配率、超负荷、均衡偏差、优先级总和、求解耗时。

自动推荐只是候选结果。正式更新 `configs/optimizer.yaml` 前，需要队友确认数据集、业务门槛和至少以下场景：正常负载、床位不足、隔离床不足、呼吸机不足、高风险患者集中到达、科室负载不均。
