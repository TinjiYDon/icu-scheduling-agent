"""Ops console theme (slate / teal clinical)."""

from __future__ import annotations

import streamlit as st

CSS = """
<style>
.stApp { background: linear-gradient(165deg, #eef2ff 0%, #f8fafc 40%, #f1f5f9 100%); }
[data-testid="stSidebar"] { background: #0f172a; }
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
.kpi-strip {
  display: flex; gap: 0.75rem; flex-wrap: wrap; margin-bottom: 1rem;
}
.kpi {
  flex: 1; min-width: 120px;
  background: #fff; border: 1px solid #e2e8f0; border-radius: 10px;
  padding: 0.85rem 1rem;
}
.kpi .lbl { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.06em; color: #64748b; }
.kpi .val { font-size: 1.5rem; font-weight: 700; color: #0f172a; margin-top: 0.2rem; }
.disclaimer {
  margin-top: 2rem; padding: 0.75rem 1rem; font-size: 0.8rem; color: #64748b;
  border-top: 1px solid #e2e8f0;
}
</style>
"""


def apply_theme() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def disclaimer() -> None:
    st.markdown(
        '<div class="disclaimer">研究演示 · 滚动 CP-SAT 仿真。candidate_cap 仅限求解候选；'
        "无 MIMIC online PPO 轨迹时勿宣称 RL 已上线。</div>",
        unsafe_allow_html=True,
    )
