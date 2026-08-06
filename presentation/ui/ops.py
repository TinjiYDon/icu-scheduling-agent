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


def _sidebar_controls() -> tuple[int, bool, str, tuple]:
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
    signature = (int(n_beds), int(cand), int(tmax), int(n_steps), policy)
    return int(n_steps), bool(auto_run), policy, signature


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
    hr = m.get("high_risk_assigned_rate", sim.get("high_risk_assigned_rate", ev.get("high_risk_assigned_rate")))
    zm = m.get("zone_match_rate", sim.get("zone_match_rate", ev.get("zone_match_rate")))
    obj = m.get("objective") or sim.get("objective") or {}

    # 行 1：求解 / 规模（每行 4 列，保证名称与数值完整显示）
    r1 = st.columns(4)
    r1[0].metric(
        "求解状态", m.get("solver_status", sim.get("solver_status", "—")),
        help="CP-SAT 求解器返回状态：OPTIMAL=找到最优解，FEASIBLE=可行解",
    )
    r1[1].metric(
        "床位数", m.get("n_beds", sim.get("n_beds", "—")),
        help="本次配置的 ICU 床位总数（含隔离床）",
    )
    r1[2].metric(
        "已分配", m.get("assigned", sim.get("assigned", "—")),
        help="被分配到床位的高危候选患者数",
    )
    r1[3].metric(
        "候选数", m.get("n_stays", sim.get("n_stays", "—")),
        help="进入求解器的候选患者数（candidate_cap 限制）",
    )

    # 行 2：占用 / 关键率
    r2 = st.columns(4)
    r2[0].metric(
        "最终占用",
        f"{sim.get('final_occupancy', '—')}/{sim.get('n_beds', '—')}",
        help="仿真结束时在床患者数 / 总床位数",
    )
    r2[1].metric(
        "利用率%", sim.get("bed_utilization_pct", "—"),
        help="仿真期间床位平均使用率（在床数÷床位数）",
    )
    r2[2].metric(
        "高危分配率", _pct(hr),
        help="SOFA≥10 的危重患者中，成功分配到床位的比例（越高越好）",
    )
    r2[3].metric(
        "Zone 匹配率", _pct(zm),
        help="被分配患者中，分到与其科室匹配的区域（MICU/SICU/CCU/NICU）的比例",
    )

    # 行 3：错配 / 耗时
    r3 = st.columns(2)
    r3[0].metric(
        "科室错配", obj.get("f4_zone_mismatch", "—"),
        help="科室错配惩罚值：分到错误区域的患者数（越小越好）",
    )
    r3[1].metric(
        "求解秒数", m.get("solve_time_seconds", ev.get("solve_time_seconds", "—")),
        help="CP-SAT 求解耗时（秒），反映实时性",
    )


def _style_high_sofa(df: pd.DataFrame) -> pd.DataFrame:
    if "sofa_total" not in df.columns:
        return df
    return df.sort_values("sofa_total", ascending=False)


def _chart_block(title: str, description: str, fig: object) -> None:
    """Render one chart on its own row with a title + plain-language caption."""
    st.markdown(f"**{title}**")
    st.caption(description)
    st.plotly_chart(fig, use_container_width=True)


def _run_selected_policy(policy: str, n_steps: int) -> dict:
    if policy == "ppo":
        return {"policy": "ppo", "ppo": run_ppo()}
    payload = run_simulation_with_plan(n_steps=n_steps)
    return {"policy": "cp_sat", **payload}


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

    n_steps, auto_enabled, policy, sig = _sidebar_controls()
    if "last_sim_payload" not in st.session_state:
        st.session_state.last_sim_payload = None
    if "ops_auto_ran" not in st.session_state:
        st.session_state.ops_auto_ran = False
    if "last_run_policy" not in st.session_state:
        st.session_state.last_run_policy = None
    if "ops_last_params" not in st.session_state:
        st.session_state.ops_last_params = sig

    # 参数变化（床位数/候选上限/求解秒数/滚动步数/策略）→ 清掉旧结果，自动重跑
    if st.session_state.ops_last_params != sig:
        st.session_state.last_sim_payload = None
        st.session_state.ops_auto_ran = False
        st.session_state.last_run_policy = None
        st.session_state.ops_last_params = sig

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
                _chart_block(
                    "① 滚动占用与入出转",
                    "折线（左轴）显示每个滚动步在床患者数；柱状（右轴）显示该步入院与出院人数。"
                    "占用接近床位数说明资源紧张。",
                    fig_occupancy_timeline(hist),
                )
                _chart_block(
                    "② 床位利用率热力",
                    "横轴为滚动步，颜色深浅表示该步的床位利用率（0~100%）。"
                    "颜色越深代表越接近满负荷。",
                    fig_occupancy_heatmap(hist, n_beds),
                )
                _chart_block(
                    "③ 在床患者平均 SOFA",
                    "横轴为滚动步，纵轴为在床患者平均 SOFA 分（0~24，越高病情越重）。"
                    "平均分上升说明当前收治患者整体更危重。",
                    fig_sofa_avg(hist),
                )
                with st.expander("滚动历史表"):
                    hist_df = pd.DataFrame(hist).rename(
                        columns={
                            "step": "步",
                            "occupied": "在床",
                            "admitted": "入院",
                            "discharged": "出院",
                            "avg_weight": "平均优先级",
                            "avg_sofa": "平均SOFA",
                            "avg_stay_steps": "平均在院(步)",
                        }
                    )
                    st.caption("每步（2 小时）的在床数、入院/出院人数、平均优先级、平均 SOFA、平均在院时长")
                    st.dataframe(hist_df, use_container_width=True, hide_index=True)
            rows = plan.get("assignments") or []
            if rows:
                st.subheader("床位分配结果（高 SOFA 优先）")
                df = _style_high_sofa(pd.DataFrame(rows))
                df = df.rename(
                    columns={
                        "stay_id": "患者ID",
                        "bed_id": "床号",
                        "bed_type": "床区",
                        "patient_zone": "患者科室",
                        "zone_match": "匹配",
                        "priority_weight": "优先级",
                        "sofa_total": "SOFA",
                    }
                )
                keep = ["患者ID", "床号", "床区", "患者科室", "匹配", "优先级", "SOFA"]
                df = df[[c for c in keep if c in df.columns]]
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.caption(
                    "床区=ICU 区域（隔离/内科/外科/心脏/新生儿）· 匹配=是否分到对应科室区域(✓/✗) · "
                    "优先级=越高越优先收治 · SOFA=危重程度(0~24 越高越重)"
                )
                if "SOFA" in df.columns:
                    hi = df[df["SOFA"].fillna(0) >= 10]
                    if len(hi):
                        st.caption(f"⚠️ 高危 SOFA≥10：{len(hi)} 人已分配（表已按 SOFA 降序）")
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
