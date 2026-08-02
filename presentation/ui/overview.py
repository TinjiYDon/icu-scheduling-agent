"""项目总览 — 答辩开场叙事。"""

from __future__ import annotations

import streamlit as st

from infra.config import load_yaml
from presentation.ui.theme import disclaimer


def render_overview() -> None:
    st.title("ICU 床位调度 · 项目总览")
    st.caption("滚动时域运筹控制台 · 默认 CP-SAT · Wave2 KPI · 禁宣称在线 PPO")

    opt = load_yaml("optimizer.yaml")
    resources = opt.get("resources") or {}
    lambdas = opt.get("lambda") or opt.get("lambdas") or {}

    st.markdown(
        """
### 要解决什么问题
在有限床位与隔离/呼吸机约束下，对排队 ICU 候选做 **多目标分配**（优先级等待、超负荷、
区域均衡、科室匹配），并在 **滚动时域**（默认每步 2h）上演示入出科与占用演化。

### 演示契约
| 项 | 定义 |
|----|------|
| 求解器 | 默认 **`cp_sat`**（OR-Tools） |
| 床位规模 | P0 演示约 **20** 床（可在运行台改 `n_beds`） |
| 滚动 | `n_steps` × step_hours；看板为占用时序 / 热力 / SOFA |
| 主 KPI | 分配率 · **高危分配率** · **zone match** · 利用率 |
| 明确不做 | **不宣称** MIMIC 上已训练可用的在线 PPO |
"""
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("配置床位数", int(resources.get("n_beds", 20)))
    c2.metric("隔离床", resources.get("n_isolation_beds", "—"))
    c3.metric("呼吸机", resources.get("n_ventilators", "—"))
    c4.metric("λ 权重键数", len(lambdas) if isinstance(lambdas, dict) else "—")

    st.markdown(
        """
### 演示路径
1. **运行**：首次进入自动跑一次 CP-SAT + 滚动仿真 → KPI · 图表 · 可解释报告  
2. **验收**：查看仿真指标与门禁说明  
3. 口播步骤见 [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md)
"""
    )
    disclaimer()
