"""Ops page: run simulation + Plotly occupancy views."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from application.plan import get_plan, run_simulation_with_plan
from application.run_ppo import run_ppo
from infra.config import load_yaml
from presentation.ui.charts import fig_occupancy_heatmap, fig_occupancy_timeline, fig_sofa_avg
from presentation.ui.theme import disclaimer

ROOT = Path(__file__).resolve().parents[2]
OPT_PATH = ROOT / "configs" / "optimizer.yaml"


def _sidebar_controls() -> tuple[int, bool, str]:
    opt = load_yaml("optimizer.yaml")
    resources = dict(opt.get("resources") or {})
    solver = dict(opt.get("solver") or {})
    policy = str(opt.get("policy", {}).get("default", "cp_sat"))
    st.sidebar.markdown("### 求解器")
    policy = st.sidebar.radio(
        "调度策略",
        options=("cp_sat", "ppo"),
        format_func=lambda value: "CP-SAT" if value == "cp_sat" else "PPO",
        index=0 if policy == "cp_sat" else 1,
    )
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
    auto_run = st.sidebar.checkbox("首次进入自动运行", value=True, key="ops_auto_run_enabled")
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
    st.sidebar.caption("ui v4 · `scripts\\run_console.ps1`")
    if policy == "ppo":
        st.sidebar.info("PPO 模式只做模型推理与分配展示，不显示滚动占用图。")
    return int(n_steps), bool(auto_run), policy


def _pct(v: object) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v) * 100:.1f}%"
    except (TypeError, ValueError):
        return str(v)


def _kpi_row(sim: dict, plan: dict) -> None:
    m = plan.get("metrics") or {}
    ev = sim.get("evaluation") or {}
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

    hr = m.get("high_risk_assigned_rate", sim.get("high_risk_assigned_rate", ev.get("high_risk_assigned_rate")))
    zm = m.get("zone_match_rate", sim.get("zone_match_rate", ev.get("zone_match_rate")))
    obj = m.get("objective") or sim.get("objective") or {}
    c2 = st.columns(4)
    c2[0].metric("高危分配率", _pct(hr))
    c2[1].metric("Zone 匹配率", _pct(zm))
    c2[2].metric("f₄ zone mismatch", obj.get("f4_zone_mismatch", "—"))
    c2[3].metric("求解秒数", m.get("solve_time_seconds", ev.get("solve_time_seconds", "—")))


def _style_high_sofa(df: pd.DataFrame) -> pd.DataFrame:
    if "sofa_total" not in df.columns:
        return df
    return df.sort_values("sofa_total", ascending=False)


def _run_selected_policy(policy: str, n_steps: int) -> dict:
    if policy == "ppo":
        return {"policy": "ppo", "ppo": run_ppo()}
    return {"policy": "cp_sat", "simulate": run_simulation_with_plan(n_steps=n_steps)}


def _render_ppo_result(result: dict) -> None:
    ppo = result.get("ppo") or {}
    reward_components = ppo.get("reward_components") or {}
    metrics = st.columns(4)
    metrics[0].metric("策略", "PPO")
    metrics[1].metric("状态", ppo.get("status", "—"))
    metrics[2].metric("已分配", ppo.get("assigned", "—"))
    metrics[3].metric("候选数", ppo.get("n_stays", "—"))

    metrics2 = st.columns(2)
    metrics2[0].metric("总奖励", ppo.get("total_reward", "—"))
    metrics2[1].metric("奖励项数", len(reward_components))

    if reward_components:
        with st.expander("奖励分解"):
            st.dataframe(
                pd.DataFrame(
                    [{"reward_component": key, "value": value} for key, value in reward_components.items()]
                ),
                use_container_width=True,
                hide_index=True,
            )

    rows = ppo.get("assignments") or []
    if rows:
        st.subheader("PPO 床位分配结果")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with st.expander("PPO JSON"):
        st.json(ppo)


def render_ops() -> None:
    st.title("ICU 床位调度 · 运行台")
    st.caption("CP-SAT 分配 + PPO 推理 + 滚动占用 · Plotly 可视化 · 首次可自动运行")

    n_steps, auto_enabled, policy = _sidebar_controls()
    if "last_sim_payload" not in st.session_state:
        st.session_state.last_sim_payload = None
    if "ops_auto_ran" not in st.session_state:
        st.session_state.ops_auto_ran = False
    if "last_run_policy" not in st.session_state:
        st.session_state.last_run_policy = None

    if st.session_state.last_run_policy and st.session_state.last_run_policy != policy:
        st.session_state.last_sim_payload = None
        st.session_state.ops_auto_ran = False

    run_col, _ = st.columns([1, 3])
    with run_col:
        run_label = "运行 PPO 推理" if policy == "ppo" else "运行 CP-SAT + 滚动仿真"
        run = st.button(run_label, type="primary", use_container_width=True)

    should_auto = (
        auto_enabled
        and not st.session_state.ops_auto_ran
        and st.session_state.last_sim_payload is None
        and not run
    )
    if should_auto:
        st.session_state.ops_auto_ran = True
        with st.spinner(f"首次进入：自动运行 {run_label}…"):
            st.session_state.last_sim_payload = _run_selected_policy(policy, n_steps)
            st.session_state.last_run_policy = policy
        st.success("自动运行完成（侧栏可关闭「首次进入自动运行」）")

    if run:
        with st.spinner("正在运行…"):
            payload = _run_selected_policy(policy, n_steps)
        st.session_state.last_sim_payload = payload
        st.session_state.ops_auto_ran = True
        st.session_state.last_run_policy = policy
        if policy == "ppo":
            ppo = payload.get("ppo") or {}
            st.success(
                f"完成 · policy=PPO · 状态={ppo.get('status', '—')} · "
                f"已分配={ppo.get('assigned', '—')} · 总奖励={ppo.get('total_reward', '—')}"
            )
        else:
            st.success(
                f"完成 · run_id={payload['plan'].get('run_id')} · "
                f"求解={payload['simulate'].get('solver_status')} · "
                f"mlflow={payload['simulate'].get('mlflow_run_id', '跳过')}"
            )

    payload = st.session_state.last_sim_payload
    if payload:
        if policy == "ppo":
            _render_ppo_result(payload)
        else:
            sim = payload["simulate"]
            plan = payload["plan"]
            _kpi_row(sim, plan)
            explain = plan.get("explain")
            with st.sidebar:
                st.markdown("### 可解释报告")
                if explain:
                    st.text(explain[:4000] if len(explain) > 4000 else explain)
                else:
                    st.caption("本次无解释文本")
            with st.expander("完整可解释报告"):
                st.code(explain or "（空）")

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
                st.subheader("床位分配结果（高 SOFA 优先列出）")
                df = _style_high_sofa(pd.DataFrame(rows))
                st.dataframe(df, use_container_width=True, hide_index=True)
                if "sofa_total" in df.columns:
                    hi = df[df["sofa_total"].fillna(0) >= 10]
                    if len(hi):
                        st.caption(f"高危 SOFA≥10：{len(hi)} 人已分配（表已按 SOFA 降序）")
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
            if policy == "ppo":
                st.info("点击 **运行 PPO 推理** 生成看板。")
            else:
                st.info("点击 **运行 CP-SAT + 滚动仿真** 生成看板。")

    disclaimer()
