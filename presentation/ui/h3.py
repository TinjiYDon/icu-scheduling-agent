"""H3：CP-SAT / Greedy / PPO 对照（离线；不宣称 online）。"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from application.h3_ui import load_comparison_table, run_h3_compare
from presentation.ui.theme import disclaimer


def render_h3() -> None:
    st.title("策略对照（H3）")
    st.caption(
        "同一套仿真环境比较 CP-SAT、贪心与 MaskablePPO。"
        "默认生产策略仍是 CP-SAT。有轨迹也不宣称 MIMIC 床旁 online PPO。"
    )
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

    if st.button("运行 evaluate_ppo（不写分配库）", type="primary"):
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
    disclaimer()
