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


def _sidebar_controls() -> tuple[int, bool, str, int, int, int]:
    opt = load_yaml("optimizer.yaml")
    resources = dict(opt.get("resources") or {})
    solver = dict(opt.get("solver") or {})
    st.sidebar.markdown("### 求解器")
    policy = st.sidebar.radio(
        "策略",
        ["cp_sat", "ppo"],
        index=0,
        format_func=lambda x: "CP-SAT（默认·演示主路径）" if x == "cp_sat" else "PPO（研究对照）",
        key="ops_policy",
        help="PPO 推理固定使用训练时床位数（默认 20）；与侧栏 CP-SAT 床位数无关",
    )
    if policy == "ppo":
        st.sidebar.caption("PPO 观测维与训练床位绑定（20 床）。改侧栏床位数只影响 CP-SAT。")
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
        _sync_solver_config(int(n_beds), int(cand), int(tmax))
        st.sidebar.success("已保存 optimizer.yaml")
    st.sidebar.caption("ui v4.2 · 点运行会自动同步床位数")
    return int(n_steps), bool(auto_run), str(policy), int(n_beds), int(cand), int(tmax)


def _sync_solver_config(n_beds: int, candidate_cap: int, max_time_seconds: int) -> None:
    """Persist sidebar solver settings and rescale ward layout to n_beds."""
    from domain.optimizer.resources import scale_bed_layout

    opt = load_yaml("optimizer.yaml")
    resources = dict(opt.get("resources") or {})
    solver = dict(opt.get("solver") or {})
    scaled = scale_bed_layout(int(n_beds))
    opt["resources"] = {**resources, **scaled}
    opt["solver"] = {
        **solver,
        "candidate_cap": int(candidate_cap),
        "max_time_seconds": int(max_time_seconds),
    }
    OPT_PATH.write_text(
        yaml.safe_dump(opt, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


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
        ("配置床位", m.get("n_beds", sim.get("n_beds", "—"))),
        ("初始分配", m.get("assigned", sim.get("assigned", "—"))),
        ("滚动后占用", f"{sim.get('final_occupancy', '—')}/{sim.get('n_beds', '—')}"),
        ("利用率%", sim.get("bed_utilization_pct", "—")),
        ("候选数", m.get("n_stays", sim.get("n_stays", "—"))),
        ("求解状态", m.get("solver_status", sim.get("solver_status", "—"))),
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


def render_ops() -> None:
    st.title("ICU 床位调度 · 运行台")
    st.caption("默认 CP-SAT + 滚动占用；可选 PPO 研究对照 · 首次可自动运行")

    from application.run_ppo import run_ppo

    n_steps, auto_enabled, policy, n_beds, cand, tmax = _sidebar_controls()
    if "last_sim_payload" not in st.session_state:
        st.session_state.last_sim_payload = None
    if "last_ppo_result" not in st.session_state:
        st.session_state.last_ppo_result = None
    if "ops_auto_ran" not in st.session_state:
        st.session_state.ops_auto_ran = False

    run_col, ppo_col, _ = st.columns([1, 1, 2])
    with run_col:
        run = st.button("运行 CP-SAT + 滚动仿真", type="primary", use_container_width=True)
    with ppo_col:
        run_ppo_btn = st.button("运行 PPO 推理", use_container_width=True, disabled=(policy != "ppo"))

    should_auto = (
        auto_enabled
        and policy == "cp_sat"
        and not st.session_state.ops_auto_ran
        and st.session_state.last_sim_payload is None
        and not run
    )
    if should_auto:
        st.session_state.ops_auto_ran = True
        _sync_solver_config(n_beds, cand, tmax)
        with st.spinner("首次进入：自动运行 CP-SAT + 滚动仿真…"):
            st.session_state.last_sim_payload = run_simulation_with_plan(n_steps=n_steps)
        st.success("自动运行完成（侧栏可关闭「首次进入自动运行」）")

    if run:
        _sync_solver_config(n_beds, cand, tmax)
        with st.spinner("SOFA → CP-SAT → 滚动仿真…"):
            payload = run_simulation_with_plan(n_steps=n_steps)
        st.session_state.last_sim_payload = payload
        st.session_state.ops_auto_ran = True
        st.success(
            f"完成 · 配置床位={n_beds} · 初始分配="
            f"{payload['plan'].get('metrics', {}).get('assigned')} · "
            f"滚动后占用={payload['simulate'].get('final_occupancy')}/"
            f"{payload['simulate'].get('n_beds')} · "
            f"求解={payload['simulate'].get('solver_status')}"
        )

    if run_ppo_btn:
        with st.spinner("加载 MaskablePPO → 推理分配…"):
            try:
                st.session_state.last_ppo_result = run_ppo()
                st.success(
                    f"PPO 完成 · assigned={st.session_state.last_ppo_result.get('assigned')} · "
                    f"reward={st.session_state.last_ppo_result.get('total_reward')} "
                    "（研究对照，非默认上线策略）"
                )
            except Exception as exc:  # noqa: BLE001
                st.error(f"PPO 失败：{exc}。确认 artifacts/ppo_icu.zip 存在且已装 sb3-contrib。")

    ppo_out = st.session_state.last_ppo_result
    if policy == "ppo" and ppo_out:
        st.subheader("PPO 分配结果（研究对照）")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("策略", "ppo")
        m2.metric("已分配", ppo_out.get("assigned"))
        m3.metric("候选", ppo_out.get("n_stays"))
        m4.metric("总奖励", ppo_out.get("total_reward"))
        st.json(ppo_out.get("reward_components") or {})
        rows = ppo_out.get("assignments") or []
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.info(
            "评估口径（B）：PPO≈73.1 vs Greedy≈73.6；默认产品路径仍为 CP-SAT。"
            "详见 docs/PPO_MODEL_HANDOFF.md"
        )

    payload = st.session_state.last_sim_payload
    if payload:
        sim = payload["simulate"]
        plan = payload["plan"]
        if policy == "cp_sat":
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
        if hist and policy == "cp_sat":
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
        if rows and policy == "cp_sat":
            st.subheader("床位分配结果（高 SOFA 优先列出）")
            df = _style_high_sofa(pd.DataFrame(rows))
            st.dataframe(df, use_container_width=True, hide_index=True)
            if "sofa_total" in df.columns:
                hi = df[df["sofa_total"].fillna(0) >= 10]
                if len(hi):
                    st.caption(f"高危 SOFA≥10：{len(hi)} 人已分配（表已按 SOFA 降序）")
        with st.expander("仿真 JSON"):
            st.json(sim)
    elif policy == "cp_sat":
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
