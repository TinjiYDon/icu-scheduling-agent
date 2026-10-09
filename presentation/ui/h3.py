"""H3：CP-SAT / Greedy / PPO 对照（离线；不宣称 online）。"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from application.h3_ui import (
    benchmark_summary_rows,
    load_benchmark,
    load_comparison_table,
    run_h3_benchmark,
    run_h3_compare,
)
from presentation.ui.theme import disclaimer


def render_h3() -> None:
    st.title("策略对照（H3）")
    st.caption(
        "同一套仿真环境比较 CP-SAT、贪心与 MaskablePPO。"
        "默认生产策略仍是 CP-SAT。有轨迹也不宣称 MIMIC 床旁 online PPO。"
    )

    tab_once, tab_multi = st.tabs(["单次对照", "多 episode 深化（S3）"])
    with tab_once:
        _render_once()
    with tab_multi:
        _render_benchmark()
    disclaimer()


def _render_once() -> None:
    loaded = load_comparison_table()
    table = loaded.get("payload") if loaded.get("status") == "ok" else None
    if table and table.get("rows"):
        st.dataframe(pd.DataFrame(table["rows"]), use_container_width=True, hide_index=True)
        if table.get("note") or table.get("h3_note"):
            st.info(table.get("note") or table.get("h3_note"))
        if table.get("fair_pool"):
            st.caption("fair_pool=true · 同 stay_ids / 床数（及报告内 shared_resources）")
        st.caption(f"来源：`{loaded.get('path')}`")
    elif loaded.get("status") == "error":
        st.error(f"无法读取对照报告：{loaded.get('error')}")
    else:
        st.info("尚无 `reports/policy_comparison.json`。可点下方按钮生成（需 PPO 检查点）。")

    if st.button("运行 evaluate_ppo（不写分配库）", type="primary", key="h3_once_run"):
        try:
            out = run_h3_compare(write_table=True)
            st.session_state["h3_table"] = out.get("payload")
            st.session_state["h3_meta"] = {
                "fair_pool": out.get("fair_pool"),
                "shared_resources": out.get("shared_resources"),
                "note": out.get("note"),
                "path": out.get("path"),
            }
            st.success(f"已写入 {out.get('path')}")
        except Exception as exc:  # noqa: BLE001
            st.error(f"对照失败：{exc}")

    live = st.session_state.get("h3_table")
    if live and live.get("rows"):
        st.subheader("本次运行")
        st.dataframe(pd.DataFrame(live["rows"]), use_container_width=True, hide_index=True)
        meta = st.session_state.get("h3_meta") or {}
        if meta.get("note"):
            st.caption(meta["note"])
        if meta.get("shared_resources"):
            with st.expander("shared_resources"):
                st.json(meta["shared_resources"])


def _render_benchmark() -> None:
    st.markdown(
        "每个 episode 抽样同一批 `stay_ids`，并强制 PPO / 贪心 / CP-SAT "
        "使用相同床位布局（隔离 / 呼吸机 / 分区）。结果写入 "
        "`reports/ppo_benchmark.json`（不入 Git）。"
    )
    loaded = load_benchmark()
    if loaded.get("status") == "ok":
        payload = loaded.get("payload") or {}
        summary = payload.get("summary") or {}
        st.caption(
            f"`{loaded.get('path')}` · episodes={summary.get('episodes')} · "
            f"fair_pool={payload.get('fair_pool')}"
        )
        rows = benchmark_summary_rows(payload)
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        if summary.get("note") or payload.get("note"):
            st.info(summary.get("note") or payload.get("note"))
    elif loaded.get("status") == "error":
        st.error(f"无法读取 benchmark：{loaded.get('error')}")
    else:
        st.info("尚无 `reports/ppo_benchmark.json`。可点下方按钮生成（需 PPO 检查点）。")

    episodes = st.number_input(
        "episode 数", min_value=1, max_value=20, value=3, key="h3_bench_episodes"
    )
    if st.button("运行多 episode 深化", type="primary", key="h3_bench_run"):
        with st.spinner("多 episode 求解中（需 artifacts/ppo_icu）…"):
            try:
                out = run_h3_benchmark(episodes=int(episodes), write_report=True)
                st.session_state["h3_bench"] = out
                st.success(f"已写入 {out.get('path')}")
            except Exception as exc:  # noqa: BLE001
                st.error(f"深化失败：{exc}")

    live = st.session_state.get("h3_bench")
    if live and live.get("rows"):
        st.subheader("本次深化摘要")
        st.dataframe(pd.DataFrame(live["rows"]), use_container_width=True, hide_index=True)
        if live.get("note"):
            st.caption(live["note"])
