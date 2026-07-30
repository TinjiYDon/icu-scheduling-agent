import pandas as pd
import streamlit as st
import yaml
from pathlib import Path

from application.plan import get_plan, run_simulation_with_plan
from infra.config import load_yaml

ROOT = Path(__file__).resolve().parents[1]
OPT_PATH = ROOT / "configs" / "optimizer.yaml"

st.set_page_config(page_title="ICU Scheduling", layout="wide")
st.title("ICU 资源动态调度")
st.caption("icu-scheduling-agent · CP-SAT · L4 · 本地调参 / MLflow")

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
if st.sidebar.button("保存配置"):
    opt["resources"] = {**resources, "n_beds": int(n_beds)}
    opt["solver"] = {**solver, "candidate_cap": int(cand), "max_time_seconds": int(tmax)}
    OPT_PATH.write_text(yaml.safe_dump(opt, allow_unicode=True, sort_keys=False), encoding="utf-8")
    st.sidebar.success("已保存 configs/optimizer.yaml")

st.sidebar.markdown("### 路径")
st.sidebar.code(str(ROOT), language=None)
st.sidebar.markdown("- 进度：`d:/project/_local-data/mimic/PROGRESS.md`")
st.sidebar.markdown("- MLflow：`mlflow ui --backend-store-uri sqlite:///./mlflow.db`")
st.sidebar.markdown("- PPO smoke：见 `docs/PPO_SMOKE.md`（Draft 分支，不合 main）")


def _render_objectives(sim: dict, plan: dict) -> None:
    m = plan.get("metrics", {})
    st.subheader("目标与约束（P0）")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("cohort stays", m.get("n_stays", sim.get("n_stays", 0)))
    c2.metric("床位数", m.get("n_beds", sim.get("n_beds", 0)))
    c3.metric("已分配", m.get("assigned", sim.get("assigned", 0)))
    c4.metric("候选 cap", m.get("n_candidates", sim.get("n_candidates", "—")))
    st.caption(
        f"求解：{m.get('solver_status', sim.get('solver_status', '—'))} · "
        f"未分配={m.get('unassigned', '—')} · "
        "全量 SOFA/labs 未裁剪；仅求解候选受限"
    )


tab_run, tab_help = st.tabs(["仿真", "学习/调参说明"])

with tab_run:
    if st.button("运行 CP-SAT 仿真", type="primary"):
        with st.spinner("SOFA → CP-SAT …"):
            payload = run_simulation_with_plan()
        sim = payload["simulate"]
        plan = payload["plan"]
        st.success(
            f"完成 · run_id={plan.get('run_id')} · solver={sim.get('solver_status')} · "
            f"mlflow={sim.get('mlflow_run_id', '（未装 mlflow 则跳过）')}"
        )
        _render_objectives(sim, plan)
        rows = plan.get("assignments", [])
        if rows:
            st.subheader("床位分配方案")
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
        else:
            st.info("无分配结果。请检查 feat.sofa_timeseries。")
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
            st.info("尚无仿真记录。点击上方按钮，或 `python -m application.simulate`。")
        else:
            st.warning(f"未找到 run_id={plan.get('run_id')} 的方案记录。")

with tab_help:
    st.markdown(
        """
### 环境与路径
| 项 | 路径 |
|----|------|
| 仓库根 | 本机 `icu-scheduling-agent/` |
| 配置 | `configs/optimizer.yaml` |
| Layer1 DB | `configs/database.yaml` → `icu_scheduling` |
| dump | `dumps/`（不入 Git） |
| MLflow | `sqlite:///./mlflow.db`（本地，gitignore） |

### 命令
```powershell
$env:PYTHONPATH = (Get-Location)
.\\.venv\\Scripts\\pip.exe install mlflow
.\\.venv\\Scripts\\python.exe -m application.simulate
.\\.venv\\Scripts\\python.exe -m mlflow ui --backend-store-uri sqlite:///./mlflow.db
streamlit run presentation/streamlit_app.py
```

### PPO
真·online 轨迹未合 main。合成 smoke：`docs/PPO_SMOKE.md`（分支 `feat/cp-sat-multi-obj`）。
"""
    )
