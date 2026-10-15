"""CareerOS — Main Streamlit Application.

Entry point for the local dashboard.
Run with:  streamlit run src/app.py
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path so imports work from any CWD.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from config.settings import settings
from src.utils.logger import setup_logging, get_logger
from src.database.connection import init_db
from src.database.migrations import run_migrations, seed_default_templates

# ── Bootstrap ─────────────────────────────────────────────────
setup_logging(settings.logging.level, settings.logging.log_file)
logger = get_logger("app")


@st.cache_resource
def _init_database():
    """Initialise DB once per Streamlit server lifecycle."""
    db = init_db(settings.database.path)
    run_migrations(db)
    seed_default_templates(db)
    logger.info("Database ready at %s", settings.database.path)
    return db


db = _init_database()

# ── Page config ───────────────────────────────────────────────
st.set_page_config(
    page_title="CareerOS",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Import font ──────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Root variables ───────────────────────────────── */
:root {
    --bg-primary: #0f172a;
    --bg-secondary: #1e293b;
    --bg-card: #1e293b;
    --border: #334155;
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --accent: #6366f1;
    --accent-glow: #818cf822;
    --success: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;
}

/* ── Base ─────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ── Sidebar ──────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f172a 0%, #1a1f3a 100%);
    border-right: 1px solid #334155;
}
[data-testid="stSidebar"] .stRadio > label {
    color: #e2e8f0 !important;
    font-weight: 500;
}
[data-testid="stSidebar"] .stRadio > div[role="radiogroup"] > label {
    padding: 0.55rem 0.75rem;
    border-radius: 8px;
    transition: background 0.15s;
}
[data-testid="stSidebar"] .stRadio > div[role="radiogroup"] > label:hover {
    background: #ffffff0a;
}
[data-testid="stSidebar"] .stRadio > div[role="radiogroup"] > label[data-checked="true"] {
    background: linear-gradient(135deg, #6366f122, #818cf811);
    border-left: 3px solid #6366f1;
}

/* ── Metric cards ─────────────────────────────────── */
.metric-card {
    background: linear-gradient(135deg, #1e293b, #1a2332);
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 1.25rem;
    text-align: center;
    transition: transform 0.15s, box-shadow 0.15s;
}
.metric-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(0,0,0,0.3);
}
.metric-icon { font-size: 1.8rem; margin-bottom: 0.3rem; }
.metric-value {
    font-size: 1.9rem;
    font-weight: 700;
    color: #f1f5f9;
    line-height: 1.2;
}
.metric-label {
    font-size: 0.82rem;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 0.15rem;
}
.metric-delta {
    font-size: 0.78rem;
    color: #10b981;
    margin-top: 0.2rem;
}

/* ── Buttons ──────────────────────────────────────── */
.stButton > button {
    border-radius: 8px;
    font-weight: 500;
    transition: all 0.15s;
    border: 1px solid #334155;
}
.stButton > button:hover {
    border-color: #6366f1;
    box-shadow: 0 0 12px #6366f122;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #6366f1, #4f46e5);
    border: none;
}

/* ── Tabs ─────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    border-bottom: 1px solid #334155;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px 8px 0 0;
    padding: 0.5rem 1.25rem;
    font-weight: 500;
    color: #94a3b8;
}
.stTabs [aria-selected="true"] {
    color: #6366f1 !important;
    border-bottom: 2px solid #6366f1;
}

/* ── Expander ─────────────────────────────────────── */
.streamlit-expanderHeader {
    font-weight: 500;
    color: #e2e8f0;
}

/* ── Smooth transitions ──────────────────────────── */
* { transition-property: background, border-color, box-shadow, color, transform; }

/* ── Logo area ────────────────────────────────────── */
.logo-area {
    text-align: center;
    padding: 1rem 0 0.5rem;
}
.logo-area h1 {
    font-size: 1.5rem;
    background: linear-gradient(135deg, #6366f1, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
    font-weight: 700;
}
.logo-area p {
    color: #64748b;
    font-size: 0.75rem;
    margin: 0;
}
</style>
""", unsafe_allow_html=True)

# ── Navigation ────────────────────────────────────────────────
PAGES = [
    ("📊", "Dashboard"),
    ("📄", "My Resumes"),
    ("✏️",  "Resume Editor"),
    ("📐", "Resume Templates"),
    ("🔍", "Find Jobs"),
    ("🎯", "Job Matching"),
    ("⚡", "Resume Optimization"),
    ("📋", "Application Tracker"),
    ("🤖", "Automation"),
    ("⚙️",  "Settings"),
]

with st.sidebar:
    st.markdown(
        '<div class="logo-area"><h1>🚀 CareerOS</h1>'
        '<p>AI-Powered Job Search</p></div>',
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # Support programmatic page switching via session_state
    default_idx = 0
    if "nav_target" in st.session_state:
        target = st.session_state.pop("nav_target")
        names = [p[1] for p in PAGES]
        if target in names:
            default_idx = names.index(target)

    selected = st.radio(
        "Navigation",
        [name for _, name in PAGES],
        index=default_idx,
        format_func=lambda x: f"{dict(PAGES)[x]} {x}",
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.caption("CareerOS v0.1.0 · Phase 1")

# ── Page router ───────────────────────────────────────────────
if selected == "Dashboard":
    from src.ui.dashboard import render
    render(db)

elif selected == "Settings":
    from src.ui.settings_page import render
    render(db)

elif selected == "My Resumes":
    from src.ui.resume_manager_page import render
    render(db)

elif selected == "Resume Editor":
    from src.ui.resume_editor_page import render
    render(db)

elif selected == "Resume Templates":
    from src.ui.resume_templates_page import render
    render(db)

elif selected == "Find Jobs":
    from src.ui.jobs_page import render
    render(db)

elif selected == "Job Matching":
    from src.ui.components import coming_soon
    coming_soon("Job Matching", "Phase 5")

elif selected == "Resume Optimization":
    from src.ui.components import coming_soon
    coming_soon("Resume Optimization", "Phase 6")

elif selected == "Application Tracker":
    from src.ui.tracker_page import render
    render(db)

elif selected == "Automation":
    from src.ui.components import coming_soon
    coming_soon("Automation", "Phase 8")
