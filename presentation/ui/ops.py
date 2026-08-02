"""Ops page: run simulation + Plotly occupancy views."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from application.plan import get_plan, run_simulation_with_plan
from infra.config import load_yaml
from presentation.ui.charts import fig_occupancy_heatmap, fig_occupancy_timeline, fig_sofa_avg
from presentation.ui.theme import disclaimer

ROOT = Path(__file__).resolve().parents[2]
OPT_PATH = ROOT / "configs" / "optimizer.yaml"


def _sidebar_controls() -> int:
    opt = load_yaml("optimizer.yaml")
    resources = dict(opt.get("resources") or {})
    solver = dict(opt.get("solver") or {})
    st.sidebar.markdown("### 求解器")
    n_beds = st.sidebar.number_input(
        "床位数 n_beds", min_value=1, max_value=200, value=int(resources.get("n_beds", 20))
    )
    cand = st.sidebar.number_input(
        "候选上限 candidate_cap",
        min_value=20,
        max_value=20000,
        value=int(solver.get("candidate_cap", 1000)),
        help="只限制 CP-SAT 候选，不删 SOFA/数据",
    )
    tmax = st.sidebar.number_input(
        "最大求解秒数",
        min_value=10,
        max_value=600,
        value=int(solver.get("max_time_seconds", 180)),
    )
    n_steps = st.sidebar.number_input("滚动步数 n_steps", min_value=1, max_value=48, value=12)
    if st.sidebar.button("保存配置", type="primary"):
        opt["resources"] = {**resources, "n_beds": int(n_beds)}
        opt["solver"] = {
            **solver,
            "candidate_cap": int(cand),
            "max_time_seconds": int(tmax),
        }
        OPT_PATH.write_text(
            yaml.safe_dump(opt, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        st.sidebar.success("已保存 optimizer.yaml")
    return int(n_steps)


def _kpi_row(sim: dict, plan: dict) -> None:
    m = plan.get("metrics") or {}
    items = [
        ("求解状态", m.get("solver_status", sim.get("solver_status", "—"))),
        ("床位数", m.get("n_beds", sim.get("n_beds", "—"))),
        ("已分配", m.get("assigned", sim.get("assigned", "—"))),
        ("最终占用", f"{sim.get('final_occupancy', '—')}/{sim.get('n_beds', '—')}"),
        ("利用率%", sim.get("bed_utilization_pct", "—")),
        ("候选数", m.get("n_stays", sim.get("n_stays", "—"))),
    ]
    cols = st.columns(len(items))
    for col, (lbl, val) in zip(cols, items):
        col.metric(lbl, val)


def render_ops() -> None:
    st.title("ICU 床位调度 · 运行台")
    st.caption("CP-SAT 分配 + 滚动占用 · Plotly 可视化")

    n_steps = _sidebar_controls()
    if "last_sim_payload" not in st.session_state:
        st.session_state.last_sim_payload = None

    run_col, _ = st.columns([1, 3])
    with run_col:
        run = st.button("运行 CP-SAT + 滚动仿真", type="primary", use_container_width=True)

    if run:
        with st.spinner("SOFA → CP-SAT → 滚动仿真…"):
            payload = run_simulation_with_plan(n_steps=n_steps)
        st.session_state.last_sim_payload = payload
        st.success(
            f"完成 · run_id={payload['plan'].get('run_id')} · "
            f"求解={payload['simulate'].get('solver_status')} · "
            f"mlflow={payload['simulate'].get('mlflow_run_id', '跳过')}"
        )

    payload = st.session_state.last_sim_payload
    if payload:
        sim = payload["simulate"]
        plan = payload["plan"]
        _kpi_row(sim, plan)
        hist = sim.get("history") or []
        n_beds = int(sim.get("n_beds") or 20)
        if hist:
            st.plotly_chart(fig_occupancy_timeline(hist), use_container_width=True)
            c1, c2 = st.columns(2)
            with c1:
                st.plotly_chart(
                    fig_occupancy_heatmap(hist, n_beds),
                    use_container_width=True,
                )
            with c2:
                st.plotly_chart(fig_sofa_avg(hist), use_container_width=True)
            with st.expander("滚动历史表"):
                st.dataframe(pd.DataFrame(hist), use_container_width=True, hide_index=True)
        rows = plan.get("assignments") or []
        if rows:
            st.subheader("床位分配结果")
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        with st.expander("仿真 JSON"):
            st.json(sim)
    else:
        plan = get_plan()
        if plan.get("status") == "ok" and plan.get("assignments"):
            st.info(f"已有方案 {plan.get('run_id')} — 再点运行可刷新滚动图")
            _kpi_row({}, plan)
            st.dataframe(
                pd.DataFrame(plan["assignments"]),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("点击 **运行 CP-SAT + 滚动仿真** 生成看板。")

    disclaimer()
