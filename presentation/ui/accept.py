"""Acceptance gates for scheduling Layer1 + last run."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from sqlalchemy import text

from infra.db import get_engine
from presentation.ui.theme import disclaimer

STATUS = Path(__file__).resolve().parents[2] / "docs" / "STATUS.md"


def render_accept() -> None:
    st.title("Acceptance gates")
    st.caption("Layer1 SOFA / staging counts + last simulation KPIs")

    try:
        engine = get_engine()
        with engine.connect() as conn:
            stays = int(conn.execute(text("SELECT COUNT(*) FROM staging.icustays")).scalar_one())
            sofa = int(
                conn.execute(text("SELECT COUNT(*) FROM feat.sofa_timeseries")).scalar_one()
            )
        g1, g2, g3 = st.columns(3)
        g1.metric("staging.icustays", f"{stays:,}")
        g2.metric("feat.sofa_timeseries", f"{sofa:,}")
        ok = stays >= 94458 * 0.99 and sofa >= 94458 * 0.99
        g3.metric("gate", "pass" if ok else "fail")
        if ok:
            st.success("Row-count gate passed (~94,458)")
        else:
            st.error("Restore icu_scheduling_P0-full_*20260802.dump")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Layer1 query failed: {exc}")

    payload = st.session_state.get("last_sim_payload")
    if payload:
        sim = payload["simulate"]
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("solver", sim.get("solver_status", "—"))
        k2.metric(
            "final occupancy",
            f"{sim.get('final_occupancy', '—')} / {sim.get('n_beds', '—')}",
        )
        k3.metric("admissions", sim.get("total_admissions", "—"))
        k4.metric("discharges", sim.get("total_discharges", "—"))
        status_ok = sim.get("solver_status") in ("OPTIMAL", "FEASIBLE")
        util = float(sim.get("bed_utilization_pct") or 0)
        if status_ok and util >= 80:
            st.success("Accept: solver OK and utilization ≥ 80%")
        elif status_ok:
            st.warning("Solver OK but utilization low")
        else:
            st.error("Solver not OPTIMAL/FEASIBLE")
    else:
        st.caption("No in-session run yet — open Ops and run once.")

    with st.expander("STATUS.md"):
        if STATUS.exists():
            st.markdown(STATUS.read_text(encoding="utf-8"))
    disclaimer()
