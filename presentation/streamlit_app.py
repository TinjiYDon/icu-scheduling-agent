import pandas as pd
import streamlit as st

from application.plan import get_plan, run_simulation_with_plan
from infra.config import load_yaml

st.set_page_config(page_title="ICU Scheduling", layout="wide")
st.title("ICU 资源动态调度")
st.caption("icu-scheduling-agent · OR-Tools CP-SAT · L4 `run_simulation_with_plan`")

opt = load_yaml("optimizer.yaml")
st.sidebar.subheader("优化器配置")
st.sidebar.json(opt.get("resources", {}))

if st.button("运行 CP-SAT 仿真", type="primary"):
    with st.spinner("SOFA → CP-SAT …"):
        payload = run_simulation_with_plan()
    sim = payload["simulate"]
    plan = payload["plan"]
    st.success(f"仿真完成 · run_id={plan.get('run_id')} · solver={sim.get('solver_status')}")

    c1, c2, c3 = st.columns(3)
    c1.metric("待分配 stays", sim.get("n_stays", 0))
    c2.metric("床位数", sim.get("n_beds", 0))
    c3.metric("已分配", sim.get("assigned", 0))

    rows = plan.get("assignments", [])
    if rows:
        st.subheader("床位分配方案")
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
    else:
        st.info("无分配结果。请先 ETL 或检查 feat.sofa_timeseries。")
else:
    plan = get_plan()
    if plan.get("status") == "ok" and plan.get("assignments"):
        st.subheader(f"最近一次方案 · {plan['run_id']}")
        st.dataframe(pd.DataFrame(plan["assignments"]), use_container_width=True)
    else:
        st.info("点击按钮运行仿真，或先执行 `python -m application.simulate`。")

st.divider()
st.caption("全链路：`python -m application.run_p0`")
