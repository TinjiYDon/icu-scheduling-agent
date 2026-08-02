from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
import yaml
from sqlalchemy import text

from application.plan import get_plan, run_simulation_with_plan
from infra.config import load_yaml
from infra.db import get_engine

ROOT = Path(__file__).resolve().parents[1]
OPT_PATH = ROOT / "configs" / "optimizer.yaml"
STATUS = ROOT / "docs" / "STATUS.md"

st.set_page_config(page_title="ICU Scheduling", layout="wide")
st.title("ICU 资源动态调度 · 交互台")
st.caption("icu-scheduling-agent · CP-SAT + 滚动仿真 · 细调 / 运行 / 验收")

opt = load_yaml("optimizer.yaml")
resources = dict(opt.get("resources") or {})
solver = dict(opt.get("solver") or {})

st.sidebar.header("调参（写入 optimizer.yaml）")
n_beds = st.sidebar.number_input("n_beds", min_value=1, max_value=200, value=int(resources.get("n_beds", 20)))
cand = st.sidebar.number_input(
    "candidate_cap",
    min_value=20,
    max_value=20000,
    value=int(solver.get("candidate_cap", 1000)),
    help="只影响 CP-SAT 候选，不删 SOFA/labs/feat",
)
tmax = st.sidebar.number_input(
    "max_time_seconds",
    min_value=10,
    max_value=600,
    value=int(solver.get("max_time_seconds", 180)),
)
n_steps = st.sidebar.number_input("rolling n_steps", min_value=1, max_value=48, value=12)
if st.sidebar.button("保存配置"):
    opt["resources"] = {**resources, "n_beds": int(n_beds)}
    opt["solver"] = {**solver, "candidate_cap": int(cand), "max_time_seconds": int(tmax)}
    OPT_PATH.write_text(yaml.safe_dump(opt, allow_unicode=True, sort_keys=False), encoding="utf-8")
    st.sidebar.success("已保存 configs/optimizer.yaml")

st.sidebar.markdown("### 路径")
st.sidebar.code(str(ROOT), language=None)
st.sidebar.markdown("- dump：`dumps/icu_scheduling_P0-full_*20260802.dump`")


def _render_objectives(sim: dict, plan: dict) -> None:
    m = plan.get("metrics", {})
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("cohort / candidates", m.get("n_stays", sim.get("n_stays", 0)))
    c2.metric("床位数", m.get("n_beds", sim.get("n_beds", 0)))
    c3.metric("已分配", m.get("assigned", sim.get("assigned", 0)))
    c4.metric("solver", m.get("solver_status", sim.get("solver_status", "—")))
    st.caption(
        f"未分配={m.get('unassigned', '—')} · "
        f"滚动最终占用={sim.get('final_occupancy', '—')}/{sim.get('n_beds', '—')} · "
        f"利用率={sim.get('bed_utilization_pct', '—')}%"
    )


tab_run, tab_timeline, tab_accept, tab_help = st.tabs(
    ["仿真运行", "占用时间线", "验收门禁", "STATUS / 说明"]
)

if "last_sim_payload" not in st.session_state:
    st.session_state.last_sim_payload = None

with tab_run:
    if st.button("运行 CP-SAT + 滚动仿真", type="primary"):
        with st.spinner("SOFA → CP-SAT → rolling …"):
            payload = run_simulation_with_plan(n_steps=int(n_steps))
        st.session_state.last_sim_payload = payload
        sim = payload["simulate"]
        plan = payload["plan"]
        st.success(
            f"完成 · run_id={plan.get('run_id')} · solver={sim.get('solver_status')} · "
            f"mlflow={sim.get('mlflow_run_id', '（未装则跳过）')}"
        )
        _render_objectives(sim, plan)
        rows = plan.get("assignments", [])
        if rows:
            st.subheader("床位分配方案")
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
        with st.expander("simulate JSON"):
            st.json(sim)
    else:
        plan = get_plan()
        status = plan.get("status")
        if status == "ok" and plan.get("assignments"):
            st.subheader(f"最近一次方案 · {plan['run_id']}")
            _render_objectives({}, plan)
            st.dataframe(pd.DataFrame(plan["assignments"]), use_container_width=True)
        elif status == "empty":
            st.info("尚无仿真记录。点击上方按钮运行。")
        else:
            st.warning(f"未找到 run_id={plan.get('run_id')} 的方案记录。")

with tab_timeline:
    payload = st.session_state.last_sim_payload
    if not payload:
        st.info("先在「仿真运行」执行一次，以生成占用时间线。")
    else:
        hist = payload["simulate"].get("history") or []
        if not hist:
            st.warning("本次结果无 history 字段")
        else:
            df = pd.DataFrame(hist)
            st.subheader("床位占用随滚动步变化")
            st.line_chart(df.set_index("step")[["occupied", "admitted", "discharged"]])
            if "avg_sofa" in df.columns:
                st.subheader("在床患者平均 SOFA")
                st.line_chart(df.set_index("step")["avg_sofa"])
            st.dataframe(df, use_container_width=True)

with tab_accept:
    st.subheader("Layer1 SOFA / staging 门禁")
    try:
        engine = get_engine()
        with engine.connect() as conn:
            stays = int(conn.execute(text("SELECT COUNT(*) FROM staging.icustays")).scalar_one())
            sofa = int(conn.execute(text("SELECT COUNT(*) FROM feat.sofa_timeseries")).scalar_one())
        g1, g2, g3 = st.columns(3)
        g1.metric("staging.icustays", f"{stays:,}")
        g2.metric("feat.sofa_timeseries", f"{sofa:,}")
        ok = stays >= 94458 * 0.99 and sofa >= 94458 * 0.99
        g3.metric("gate", "pass" if ok else "fail")
        if ok:
            st.success("行数门禁通过（≈94,458）")
        else:
            st.error("请 restore `icu_scheduling_P0-full_*20260802.dump`")
    except Exception as exc:  # noqa: BLE001
        st.error(f"无法查询 Layer1：{exc}")

    payload = st.session_state.last_sim_payload
    if payload:
        sim = payload["simulate"]
        st.subheader("最近一次运行 KPI")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("solver", sim.get("solver_status", "—"))
        k2.metric("最终占用", f"{sim.get('final_occupancy', '—')} / {sim.get('n_beds', '—')}")
        k3.metric("入院", sim.get("total_admissions", "—"))
        k4.metric("出院", sim.get("total_discharges", "—"))
        status_ok = sim.get("solver_status") in ("OPTIMAL", "FEASIBLE")
        util = float(sim.get("bed_utilization_pct") or 0)
        if status_ok and util >= 80:
            st.success("验收：求解成功且利用率 ≥ 80%")
        elif status_ok:
            st.warning("求解成功但利用率偏低，检查 n_beds / 候选")
        else:
            st.error("求解未达 OPTIMAL/FEASIBLE")

with tab_help:
    if STATUS.exists():
        st.markdown(STATUS.read_text(encoding="utf-8"))
    st.markdown(
        """
### 命令
```powershell
$env:PYTHONPATH = (Get-Location)
.\\scripts\\restore_layer1.ps1 -DumpFile .\\dumps\\icu_scheduling_P0-full_mimic_94458stays_20260802.dump
streamlit run presentation/streamlit_app.py
```
"""
    )
