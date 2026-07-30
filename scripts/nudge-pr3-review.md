## PR Review · #3 Draft（保持 Draft · PPO 不合 main）

@Mengziyang111 @Hongejek 感谢 lambda 归一化 + MaskablePPO 工作流。集成负责人（C）审查结论如下。

### 人读摘要

| 项 | 内容 |
|----|------|
| Owner | B 算法 · C 集成审 |
| 结论 | **保持 Draft**；默认 `policy=cp_sat` |
| 可拆合（另开 PR） | lambda 权重校验 + 目标归一化 + 审计字段 |
| 暂不合 | PPO / Gym env / hybrid 默认路径 |

### 必须说明 / 清理

1. 去掉无意义 commit（`just a test` / `clean`）或 squash 后再 Ready
2. 全量 PPO 训练依赖 PostgreSQL/MIMIC；**schemas_only dump 不够**（见 `docs/PARAM_STORY.md`）
3. 合并策略：优先拆 **lambda-only** PR；PPO 继续预研直至有 `sim` 轨迹表
4. 仓库 RL 路线：`B（数据故事）+ C（decision 不做 RL）+ A审（本 PR）`；行为克隆（D）后置

### 验收（本地）

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m pytest tests/test_lambda_weights.py tests/test_rl_env.py -q
```

关联：`docs/STATUS.md` · `docs/PARAM_STORY.md` · BACKLOG `#S4-1`
