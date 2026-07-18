# λ 权重调优说明

## 目的

λ 控制 CP-SAT 在患者优先级、超负荷、区域均衡和科室匹配之间的取舍。配置可运行不等于参数已经调优；只有固定数据和场景上的实验结果才能形成推荐值。

## 执行

快速敏感性实验：

```powershell
python scripts/tune_lambda.py --quick
```

完整 256 组合实验：

```powershell
python scripts/tune_lambda.py
```

输出文件：

- `reports/lambda_tuning.csv`：全部实验。
- `reports/lambda_tuning_pareto.csv`：非支配解。
- `reports/lambda_tuning_recommended.json`：按公开排序规则选择的建议组合。

## 选择规则

程序不比较不同 λ 下不可比的求解器总目标值，而是比较原始业务指标。推荐顺序为：高风险患者分配率、科室匹配率、超负荷、均衡偏差、优先级总和、求解耗时。

自动推荐只是候选结果。正式更新 `configs/optimizer.yaml` 前，需要队友确认数据集、业务门槛和至少以下场景：正常负载、床位不足、隔离床不足、呼吸机不足、高风险患者集中到达、科室负载不均。
