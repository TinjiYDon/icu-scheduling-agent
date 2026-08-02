"""ICU scheduling ops console — Streamlit + Plotly."""

from __future__ import annotations

import streamlit as st

from presentation.ui.accept import render_accept
from presentation.ui.ops import render_ops
from presentation.ui.theme import apply_theme

st.set_page_config(
    page_title="ICU Bed Ops",
    page_icon="🛏️",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_theme()

ops_page = st.Page(render_ops, title="Ops", icon=":material/bed:", default=True)
accept_page = st.Page(render_accept, title="Accept", icon=":material/verified:")

nav = st.navigation([ops_page, accept_page])
nav.run()
