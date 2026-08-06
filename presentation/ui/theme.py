"""调度 Ops 台主题（依赖 `.streamlit/config.toml` 强制 Light Theme + 侧栏高对比 + KPI 卡片）。"""

from __future__ import annotations

import streamlit as st

CSS = """
<style>
/* 全局：在 Streamlit Light Theme 之上叠加一层柔和渐变背景（不影响官方组件颜色体系） */
.stApp { background: linear-gradient(165deg, #eef5f3 0%, #f8fafc 40%, #f1f5f9 100%); }

/* 兜底：主区域核心文字容器再盖一层深墨色，防 Light Theme 偶发继承出浅字 */
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
.stApp [data-testid="stMarkdownContainer"],
.stApp [data-testid="stMarkdownContainer"] *,
.stApp [data-testid="stCaptionContainer"],
.stApp [data-testid="stCaptionContainer"] *,
.stApp [data-testid="stSubheaderContainer"],
.stApp [data-testid="stSubheaderContainer"] *,
.stApp label,
.stApp label *,
.stApp p, .stApp span, .stApp li, .stApp small {
  color: #0f172a;
}
.stApp [data-testid="stMarkdownContainer"] code,
.stApp code {
  color: #0f172a;
  background-color: #e2e8f0;
  padding: 0.1rem 0.3rem;
  border-radius: 3px;
}

/* KPI metric 卡片：白底 + 灰边框 + 区分标签/数值色（避免 Light Theme 下无边框太扁） */
.stApp [data-testid="stMetric"] {
  background-color: #ffffff;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 0.6rem 0.9rem;
  box-shadow: 0 1px 2px rgba(15,23,42,0.04);
}
.stApp [data-testid="stMetricLabel"],
.stApp [data-testid="stMetricLabel"] * {
  color: #475569;
  font-weight: 500;
}
.stApp [data-testid="stMetricValue"],
.stApp [data-testid="stMetricValue"] * {
  color: #0f172a;
  font-weight: 700;
}
.stApp [data-testid="stMetricDelta"] * {
  color: #0f766e;
}

/* 侧栏深色 + 白字（不被 Light Theme 冲掉，侧栏作为导航区保持高对比） */
[data-testid="stSidebar"] { background: #0f172a !important; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] *,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] small {
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
/* 侧栏 help text / caption 再兜底（Light Theme 下侧栏 caption 易变深色） */
[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] * {
  color: #94a3b8 !important;
}

/* 原生 Tab 标签（非侧栏）：高亮条用主色 teal，保证文字清楚 */
.stApp [data-baseweb="tab-list"] button,
.stApp [data-baseweb="tab-list"] button * { color: #0f172a; }
.stApp [data-baseweb="tab-highlight"] { background-color: #0f766e !important; }

/* 底部免责声明 */
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
