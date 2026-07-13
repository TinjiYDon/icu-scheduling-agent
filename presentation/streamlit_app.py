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


def _render_objectives(sim: dict, plan: dict) -> None:
    m = plan.get("metrics", {})
    st.subheader("目标与约束（P0）")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("待分配 stays", m.get("n_stays", sim.get("n_stays", 0)))
    c2.metric("床位数", m.get("n_beds", sim.get("n_beds", 0)))
    c3.metric("已分配", m.get("assigned", sim.get("assigned", 0)))
    c4.metric("未分配", m.get("unassigned", 0))
    st.caption(
        f"求解状态：{m.get('solver_status', sim.get('solver_status', '—'))} · "
        "目标：最大化 Σ(priority_weight×分配) · 约束：每床≤1人、每人≤1床"
    )


if st.button("运行 CP-SAT 仿真", type="primary"):
    with st.spinner("SOFA → CP-SAT …"):
        payload = run_simulation_with_plan()
    sim = payload["simulate"]
    plan = payload["plan"]
    st.success(f"仿真完成 · run_id={plan.get('run_id')} · solver={sim.get('solver_status')}")
    _render_objectives(sim, plan)
    rows = plan.get("assignments", [])
    if rows:
        st.subheader("床位分配方案")
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
    else:
        st.info("无分配结果。请先 ETL 或检查 feat.sofa_timeseries。")
else:
    plan = get_plan()
    status = plan.get("status")
    if status == "ok" and plan.get("assignments"):
        st.subheader(f"最近一次方案 · {plan['run_id']}")
        _render_objectives({}, plan)
        st.dataframe(pd.DataFrame(plan["assignments"]), use_container_width=True)
    elif status == "empty":
        st.info("尚无仿真记录。点击上方按钮运行，或先执行 `python -m application.simulate`。")
    else:
        st.warning(f"未找到 run_id={plan.get('run_id')} 的方案记录。")

st.divider()
st.caption("全链路：`python -m application.run_p0`")
