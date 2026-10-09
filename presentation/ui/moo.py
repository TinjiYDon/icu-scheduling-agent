"""S2-MOO 三模式对照（阶段 5 演示）。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from domain.optimizer.moo_display import (
    epsilon_bounds_from_phase3,
    load_latest_phase3,
    load_latest_scenarios,
    pivot_scenario_rows,
    three_mode_metrics,
)
from domain.optimizer.moo_scenarios import DEFAULT_EPSILON_BOUNDS
from presentation.ui.theme import disclaimer

ROOT = Path(__file__).resolve().parents[2]


def render_moo() -> None:
    st.title("多目标方法对照")
    st.caption(
        "底座仍是 CP-SAT 硬约束；本页只换决策机理："
        "加权和 / 词典序 / ε-约束。PPO 不在本页。"
    )
    st.markdown(
        "- **加权和**：一组 λ，一个折中解（基线）。  \n"
        "- **词典序**：先锁占床，再锁高危，再优化优先级总和。  \n"
        "- **ε-约束**：其余目标变成底线，扫描 Pareto 候选。"
    )

    phase3 = load_latest_phase3(ROOT)
    if phase3:
        st.subheader("阶段 3 摘要（本地 reports/moo）")
        scan = phase3.get("scan") or {}
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("网格点数", scan.get("n_grid", "—"))
        c2.metric("可行", scan.get("n_feasible", "—"))
        c3.metric("非支配", scan.get("n_nondominated", "—"))
        hv = scan.get("hypervolume")
        c4.metric("超体积 HV", f"{hv:.4f}" if isinstance(hv, (int, float)) else "—")
    else:
        st.info("未找到 `reports/moo/summary_latest.json`（该目录不入 Git）。可先跑 `python -m application.run_moo_phase3`。")

    scenarios = load_latest_scenarios(ROOT)
    st.subheader("阶段 4 六场景宽表")
    if scenarios:
        wide = pivot_scenario_rows(list(scenarios.get("rows") or []))
        if wide:
            st.dataframe(pd.DataFrame(wide), use_container_width=True, hide_index=True)
        else:
            st.caption("JSON 中没有 rows。")
    else:
        st.info("未找到 `reports/moo/scenarios_latest.json`。可先跑 `python -m application.run_moo_phase4 --split calib`。")

    st.subheader("当场三模式（calib · 不写库）")
    st.caption("求解可能各数十秒；请用短时限。失败时看状态，不要改硬约束去「凑可行」。")
    max_t = st.number_input("每模式最大秒数", min_value=5, max_value=120, value=20)
    if st.button("运行加权 + 词典序 + ε-约束", type="primary"):
        from domain.optimizer.cp_sat import run_assignment

        rows = []
        with st.spinner("weighted_sum…"):
            ws = run_assignment(
                persist=False,
                split="calib",
                objective_mode="weighted_sum",
                max_time_seconds=float(max_t),
            )
            rows.append(three_mode_metrics(ws))
        with st.spinner("lexicographic…"):
            lex = run_assignment(
                persist=False,
                split="calib",
                objective_mode="lexicographic",
                max_time_seconds=float(max_t),
            )
            rows.append(three_mode_metrics(lex))
        bounds = epsilon_bounds_from_phase3(phase3) or dict(DEFAULT_EPSILON_BOUNDS)
        st.caption(f"ε 边界：{bounds}")
        with st.spinner("epsilon_constraint…"):
            eps = run_assignment(
                persist=False,
                split="calib",
                objective_mode="epsilon_constraint",
                epsilon_primary="wait",
                epsilon_bounds=bounds,
                max_time_seconds=float(max_t),
            )
            rows.append(three_mode_metrics(eps))
        st.session_state["moo_live_rows"] = rows
        st.success("三种机理已跑完。不可行请看 status，完整网格仍用 phase3 CLI。")

    live = st.session_state.get("moo_live_rows")
    if live:
        st.dataframe(pd.DataFrame(live), use_container_width=True, hide_index=True)

    disclaimer()
