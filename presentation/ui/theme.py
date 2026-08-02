"""调度 Ops 台主题（侧栏高对比）。"""

from __future__ import annotations

import streamlit as st

CSS = """
<style>
.stApp { background: linear-gradient(165deg, #eef5f3 0%, #f8fafc 40%, #f1f5f9 100%); }
[data-testid="stSidebar"] { background: #0f172a !important; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
  color: #e2e8f0 !important;
}
[data-testid="stSidebar"] button {
  background-color: #2dd4bf !important;
  color: #0f172a !important;
  border: 1px solid #0f766e !important;
  font-weight: 700 !important;
}
[data-testid="stSidebar"] button p,
[data-testid="stSidebar"] button span,
[data-testid="stSidebar"] button div {
  color: #0f172a !important;
  font-weight: 700 !important;
}
[data-testid="stSidebarNav"] a,
[data-testid="stSidebarNav"] span { color: #e2e8f0 !important; }
[data-testid="stSidebarNav"] [aria-selected="true"] {
  background-color: #334155 !important;
}
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
        '<div class="disclaimer">研究演示 · 滚动 CP-SAT 仿真。candidate_cap 只限制求解候选；'
        "无 MIMIC online PPO 轨迹时勿宣称强化学习已上线。</div>",
        unsafe_allow_html=True,
    )
