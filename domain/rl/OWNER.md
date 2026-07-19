# PPO / 强化学习模块

- **主责**：成员 B（算法/优化）。
- **当前入口**：`domain/rl/env.py::ICUEnv`。
- **输入契约**：调用方构造固定 episode 的 `Patient` 与 `Bed`；环境本身不查数据库。
- **动作契约**：`0..n_beds-1` 选择床，`n_beds` 表示继续等待。
- **约束契约**：训练和推理必须使用 `action_masks()`，不能只依靠非法动作惩罚。
- **训练入口**：`python -m application.train_ppo`。
- **推理入口**：`python -m application.run_ppo`。
- **下一交付**：运行测试、训练模型，并完成 PPO/CP-SAT 留出场景评估。
