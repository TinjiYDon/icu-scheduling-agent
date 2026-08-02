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
    st.sidebar.markdown("### Solver")
    n_beds = st.sidebar.number_input(
        "n_beds", min_value=1, max_value=200, value=int(resources.get("n_beds", 20))
    )
    cand = st.sidebar.number_input(
        "candidate_cap",
        min_value=20,
        max_value=20000,
        value=int(solver.get("candidate_cap", 1000)),
        help="Caps CP-SAT candidates only",
    )
    tmax = st.sidebar.number_input(
        "max_time_seconds",
        min_value=10,
        max_value=600,
        value=int(solver.get("max_time_seconds", 180)),
    )
    n_steps = st.sidebar.number_input("rolling n_steps", min_value=1, max_value=48, value=12)
    if st.sidebar.button("Save config"):
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
        st.sidebar.success("Saved optimizer.yaml")
    return int(n_steps)


def _kpi_row(sim: dict, plan: dict) -> None:
    m = plan.get("metrics") or {}
    items = [
        ("solver", m.get("solver_status", sim.get("solver_status", "—"))),
        ("beds", m.get("n_beds", sim.get("n_beds", "—"))),
        ("assigned", m.get("assigned", sim.get("assigned", "—"))),
        ("occupancy", f"{sim.get('final_occupancy', '—')}/{sim.get('n_beds', '—')}"),
        ("util %", sim.get("bed_utilization_pct", "—")),
        ("candidates", m.get("n_stays", sim.get("n_stays", "—"))),
    ]
    cols = st.columns(len(items))
    for col, (lbl, val) in zip(cols, items):
        col.metric(lbl, val)


def render_ops() -> None:
    st.title("ICU Bed Ops Console")
    st.caption("CP-SAT assignment + rolling-horizon occupancy · Plotly views")

    n_steps = _sidebar_controls()
    if "last_sim_payload" not in st.session_state:
        st.session_state.last_sim_payload = None

    run_col, _ = st.columns([1, 3])
    with run_col:
        run = st.button("Run CP-SAT + rolling", type="primary", use_container_width=True)

    if run:
        with st.spinner("SOFA → CP-SAT → rolling…"):
            payload = run_simulation_with_plan(n_steps=n_steps)
        st.session_state.last_sim_payload = payload
        st.success(
            f"run_id={payload['plan'].get('run_id')} · "
            f"solver={payload['simulate'].get('solver_status')} · "
            f"mlflow={payload['simulate'].get('mlflow_run_id', 'skip')}"
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
            with st.expander("history table"):
                st.dataframe(pd.DataFrame(hist), use_container_width=True, hide_index=True)
        rows = plan.get("assignments") or []
        if rows:
            st.subheader("Bed assignments")
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        with st.expander("simulate JSON"):
            st.json(sim)
    else:
        plan = get_plan()
        if plan.get("status") == "ok" and plan.get("assignments"):
            st.info(f"Cached plan {plan.get('run_id')} — run again for rolling charts")
            _kpi_row({}, plan)
            st.dataframe(
                pd.DataFrame(plan["assignments"]),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Click **Run CP-SAT + rolling** to populate the ops dashboard.")

    disclaimer()
