"""S2-MOO 三模式对照（阶段 5 演示）。"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from application.moo_ui import (
    flatten_front,
    load_phase3_summary,
    load_scenarios_latest,
    rows_to_csv,
    run_three_mode_live,
    scenario_wide_table,
)
from presentation.ui.charts import fig_pareto_2d
from presentation.ui.theme import disclaimer


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

    summary = load_phase3_summary()
    phase3 = summary.get("payload") if summary.get("status") == "ok" else None
    if phase3:
        st.subheader("阶段 3 摘要（本地 reports/moo）")
        scan = phase3.get("scan") or {}
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("网格点数", scan.get("n_grid", "—"))
        c2.metric("可行", scan.get("n_feasible", "—"))
        c3.metric("非支配", scan.get("n_nondominated", "—"))
        hv = scan.get("hypervolume")
        c4.metric("超体积 HV", f"{hv:.4f}" if isinstance(hv, (int, float)) else "—")
        front = list(phase3.get("front") or [])
        if front:
            st.subheader("Pareto 散点")
            axes = ["wait", "high_risk", "occupancy", "overload", "balance"]
            x_col, y_col = st.columns(2)
            x_obj = x_col.selectbox("横轴", axes, index=0, key="pareto_x")
            y_obj = y_col.selectbox("纵轴", axes, index=1, key="pareto_y")
            st.plotly_chart(
                fig_pareto_2d(front, x_obj=x_obj, y_obj=y_obj),
                use_container_width=True,
            )
            front_rows = flatten_front(front)
            st.download_button(
                "下载 Pareto CSV",
                data=rows_to_csv(front_rows),
                file_name="moo_pareto_front.csv",
                mime="text/csv",
                key="dl_front",
            )
    else:
        st.info(
            "未找到 `reports/moo/summary_latest.json`（该目录不入 Git）。"
            "可先跑 `python -m application.run_moo_phase3`。"
        )

    scenarios = load_scenarios_latest()
    st.subheader("阶段 4 六场景宽表")
    if scenarios.get("status") == "ok":
        wide = scenario_wide_table(scenarios.get("payload"))
        if wide:
            st.dataframe(pd.DataFrame(wide), use_container_width=True, hide_index=True)
            st.download_button(
                "下载场景 CSV",
                data=rows_to_csv(wide),
                file_name="moo_scenarios.csv",
                mime="text/csv",
                key="dl_scenarios",
            )
        else:
            st.caption("JSON 中没有 rows。")
    else:
        st.info(
            "未找到 `reports/moo/scenarios_latest.json`。"
            "可先跑 `python -m application.run_moo_phase4 --split calib`。"
        )

    st.subheader("当场三模式（calib · 不写库）")
    st.caption("求解可能各数十秒；请用短时限。失败时看状态，不要改硬约束去「凑可行」。")
    max_t = st.number_input("每模式最大秒数", min_value=5, max_value=120, value=20)
    if st.button("运行加权 + 词典序 + ε-约束", type="primary"):
        with st.spinner("三模式求解中…"):
            live = run_three_mode_live(
                split="calib",
                max_time_seconds=float(max_t),
                persist=False,
                phase3=phase3,
            )
        st.session_state["moo_live"] = live
        st.caption(f"ε 边界：{live.get('epsilon_bounds')}")
        st.success("三种机理已跑完。不可行请看 status，完整网格仍用 phase3 CLI。")

    live = st.session_state.get("moo_live")
    if live and live.get("rows"):
        st.dataframe(pd.DataFrame(live["rows"]), use_container_width=True, hide_index=True)
        st.download_button(
            "下载本次对照 CSV",
            data=rows_to_csv(list(live["rows"])),
            file_name="moo_live_three_mode.csv",
            mime="text/csv",
            key="dl_live",
        )

    disclaimer()
