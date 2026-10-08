"""H3：CP-SAT / Greedy / PPO 对照（离线；不宣称 online）。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from domain.ops.policy_comparison import flatten_comparison
from presentation.ui.theme import disclaimer

ROOT = Path(__file__).resolve().parents[2]
TABLE = ROOT / "reports" / "policy_comparison.json"
RAW = ROOT / "reports" / "ppo_evaluation.json"


def _load_table() -> dict | None:
    import json

    if TABLE.is_file():
        return json.loads(TABLE.read_text(encoding="utf-8"))
    if RAW.is_file():
        raw = json.loads(RAW.read_text(encoding="utf-8"))
        if "rows" in raw:
            return raw
        return flatten_comparison(raw)
    return None


def render_h3() -> None:
    st.title("策略对照（H3）")
    st.caption(
        "同一套仿真环境比较 CP-SAT、贪心与 MaskablePPO。"
        "默认生产策略仍是 CP-SAT。有轨迹也不宣称 MIMIC 床旁 online PPO。"
    )
    table = _load_table()
    if table and table.get("rows"):
        st.dataframe(pd.DataFrame(table["rows"]), use_container_width=True, hide_index=True)
        if table.get("h3_note"):
            st.info(table["h3_note"])
    else:
        st.info("尚无 `reports/policy_comparison.json`。可点下方按钮生成（需 PPO 检查点）。")

    if st.button("运行 evaluate_ppo（不写分配库）", type="primary"):
        try:
            from application.evaluate_ppo import evaluate_ppo
            import json

            report = evaluate_ppo()
            flat = report.get("comparison_table") or flatten_comparison(report)
            out = ROOT / "reports" / "policy_comparison.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(flat, ensure_ascii=False, indent=2), encoding="utf-8")
            st.session_state["h3_table"] = flat
            st.success("已写入 reports/policy_comparison.json")
        except Exception as exc:  # noqa: BLE001
            st.error(f"对照失败：{exc}")

    live = st.session_state.get("h3_table")
    if live and live.get("rows"):
        st.subheader("本次运行")
        st.dataframe(pd.DataFrame(live["rows"]), use_container_width=True, hide_index=True)
    disclaimer()
