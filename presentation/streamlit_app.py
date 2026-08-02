"""ICU 床位调度 Ops 台 — Streamlit + Plotly。"""

from __future__ import annotations

import streamlit as st

from presentation.ui.accept import render_accept
from presentation.ui.ops import render_ops
from presentation.ui.theme import apply_theme

st.set_page_config(
    page_title="ICU 床位调度",
    page_icon="🛏️",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_theme()

ops_page = st.Page(render_ops, title="运行", icon=":material/bed:", default=True)
accept_page = st.Page(render_accept, title="验收", icon=":material/verified:")

nav = st.navigation([ops_page, accept_page])
nav.run()
