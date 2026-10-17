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
    page_title="CareerOS · AI Career Platform",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS & Design System ────────────────────────────────
st.markdown("""
<style>
/* ── Typography & Google Fonts ────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');

/* ── Modern Design Tokens ─────────────────────────── */
:root {
    --bg-primary: #090d16;
    --bg-secondary: #0f172a;
    --bg-card: #131b2e;
    --border: #1e293b;
    --border-accent: #334155;
    --text-primary: #f8fafc;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --accent: #6366f1;
    --accent-hover: #4f46e5;
    --accent-glow: rgba(99, 102, 241, 0.2);
    --success: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;
}

/* ── Base App Container ───────────────────────────── */
html, body, [data-testid="stAppViewContainer"] {
    font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background-color: var(--bg-primary);
    color: var(--text-primary);
}

[data-testid="stAppViewContainer"] > .main {
    padding-top: 1rem;
}

/* ── Sidebar ──────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #090d16 0%, #0f172a 100%);
    border-right: 1px solid var(--border);
}

[data-testid="stSidebar"] .stRadio > div[role="radiogroup"] {
    gap: 4px;
}

[data-testid="stSidebar"] .stRadio > div[role="radiogroup"] > label {
    padding: 0.55rem 0.85rem;
    border-radius: 8px;
    border: 1px solid transparent;
    transition: all 0.18s ease-in-out;
    color: #cbd5e1 !important;
    font-size: 0.92rem;
    font-weight: 500;
}

[data-testid="stSidebar"] .stRadio > div[role="radiogroup"] > label:hover {
    background: #1e293b88;
    color: #f8fafc !important;
    border-color: #334155;
}

[data-testid="stSidebar"] .stRadio > div[role="radiogroup"] > label[data-checked="true"] {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.22) 0%, rgba(79, 70, 229, 0.1) 100%);
    border: 1px solid rgba(99, 102, 241, 0.4);
    border-left: 3.5px solid #6366f1;
    color: #ffffff !important;
    font-weight: 600;
    box-shadow: 0 4px 14px rgba(99, 102, 241, 0.15);
}

/* ── Metric Cards ─────────────────────────────────── */
.metric-card {
    background: linear-gradient(145deg, #131b2e 0%, #0e1526 100%);
    border: 1px solid #1e293b;
    border-radius: 14px;
    padding: 1.25rem 1rem;
    text-align: center;
    transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s, border-color 0.2s;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
    position: relative;
    overflow: hidden;
}

.metric-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, transparent, #6366f166, transparent);
}

.metric-card:hover {
    transform: translateY(-3px);
    border-color: #3b82f6;
    box-shadow: 0 8px 30px rgba(99, 102, 241, 0.2);
}

.metric-icon { font-size: 1.85rem; margin-bottom: 0.35rem; }

.metric-value {
    font-size: 1.95rem;
    font-weight: 700;
    color: #f8fafc;
    line-height: 1.2;
    letter-spacing: -0.02em;
}

.metric-label {
    font-size: 0.8rem;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
    margin-top: 0.25rem;
}

.metric-delta {
    font-size: 0.78rem;
    color: #10b981;
    font-weight: 600;
    margin-top: 0.25rem;
}

/* ── Buttons ──────────────────────────────────────── */
.stButton > button {
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.88rem;
    letter-spacing: 0.01em;
    padding: 0.45rem 1rem;
    transition: all 0.15s ease-in-out;
    border: 1px solid #334155;
    background-color: #172033;
    color: #f1f5f9;
}

.stButton > button:hover {
    border-color: #6366f1;
    color: #ffffff;
    box-shadow: 0 0 16px rgba(99, 102, 241, 0.25);
    transform: translateY(-1px);
}

.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
    border: 1px solid #818cf8;
    color: #ffffff;
    box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);
}

.stButton > button[kind="primary"]:hover {
    box-shadow: 0 6px 20px rgba(99, 102, 241, 0.45);
    transform: translateY(-1.5px);
}

/* ── Tabs ─────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    border-bottom: 1px solid #1e293b;
    padding-bottom: 4px;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 8px 8px 0 0;
    padding: 0.6rem 1.25rem;
    font-weight: 600;
    font-size: 0.9rem;
    color: #94a3b8;
    border: none;
    transition: all 0.15s;
}

.stTabs [aria-selected="true"] {
    color: #818cf8 !important;
    background: #1e293b66;
    border-bottom: 2.5px solid #6366f1 !important;
}

/* ── Expanders ────────────────────────────────────── */
.streamlit-expanderHeader {
    font-weight: 600;
    color: #f1f5f9;
    background-color: #131b2e !important;
    border-radius: 8px;
}

[data-testid="stExpander"] {
    border: 1px solid #1e293b;
    border-radius: 10px;
    background-color: #0d1424;
    margin-bottom: 0.75rem;
}

/* ── Logo Area ────────────────────────────────────── */
.logo-area {
    text-align: center;
    padding: 0.75rem 0 0.5rem;
}

.logo-area h1 {
    font-size: 1.55rem;
    background: linear-gradient(135deg, #818cf8 0%, #c084fc 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
    font-weight: 800;
    letter-spacing: -0.02em;
}

.logo-area p {
    color: #64748b;
    font-size: 0.75rem;
    font-weight: 500;
    margin: 2px 0 0;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}
</style>
""", unsafe_allow_html=True)

# ── Navigation Architecture ───────────────────────────────────
PAGES = [
    ("📊", "Dashboard"),
    ("📄", "My Resumes"),
    ("✏️", "Resume Editor"),
    ("👁️", "Resume Preview"),
    ("⚡", "Resume Optimization"),
    ("📐", "Resume Templates"),
    ("🔍", "Find Jobs"),
    ("🎯", "Job Matching"),
    ("📋", "Application Tracker"),
    ("🤖", "Automation"),
    ("🔌", "API & Extension"),
    ("⚙️", "Settings"),
]
PAGE_ICONS = {name: emoji for emoji, name in PAGES}
PAGE_NAMES = [name for _, name in PAGES]

# ── Sidebar Navigation & Active Status ────────────────────────
with st.sidebar:
    st.markdown(
        '<div class="logo-area"><h1>🚀 CareerOS</h1>'
        '<p>AI Career Platform</p></div>',
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # Active Resume Widget in Sidebar
    from src.resume.repository import ResumeRepository
    from src.resume.sample_data import create_sample_mba_resume

    repo = ResumeRepository(db)
    resumes = repo.list_resumes()
    if resumes:
        active_id = st.session_state.get("active_resume_id", resumes[0].id)
        active_res = next((r for r in resumes if r.id == active_id), resumes[0])
        st.session_state["active_resume_id"] = active_res.id

        master_badge = " ⭐ MASTER" if active_res.is_master else ""
        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, #131b2e 0%, #0d1424 100%);
                        border: 1px solid #1e293b; border-radius: 8px; padding: 10px; margin-bottom: 10px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:0.7rem; color:#94a3b8; font-weight:700; letter-spacing:0.05em; text-transform:uppercase;">Active Resume</span>
                    <span style="font-size:0.68rem; color:#818cf8; font-weight:700;">{master_badge}</span>
                </div>
                <div style="font-size:0.88rem; font-weight:600; color:#f8fafc; margin:3px 0 8px 0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                    {active_res.name}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        side_c1, side_c2 = st.columns(2)
        with side_c1:
            if st.button("✏️ Edit", key="sidebar_edit_btn", use_container_width=True):
                st.session_state["active_page"] = "Resume Editor"
                st.rerun()
        with side_c2:
            if st.button("👁️ View", key="sidebar_pv_btn", type="primary", use_container_width=True):
                st.session_state["active_page"] = "Resume Preview"
                st.rerun()
    else:
        st.markdown(
            """
            <div style="background: #1e293b44; border: 1px dashed #334155; border-radius: 8px; padding: 10px; text-align:center; margin-bottom: 10px;">
                <div style="font-size:0.78rem; color:#94a3b8; margin-bottom:6px;">No Resumes Loaded</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("✨ Load MBA Resume", key="side_seed_mba", type="primary", use_container_width=True):
            r_id, v_id = create_sample_mba_resume(repo)
            st.session_state["active_resume_id"] = r_id
            st.session_state["active_version_id"] = v_id
            st.session_state["active_page"] = "Resume Preview"
            st.rerun()

    st.markdown("---")

    # Programmatic navigation synchronization
    if "nav_target" in st.session_state:
        st.session_state["active_page"] = st.session_state.pop("nav_target")

    current_target = st.session_state.get("active_page")
    if current_target and current_target in PAGE_NAMES:
        st.session_state["app_main_navigation_radio"] = current_target
    elif "app_main_navigation_radio" not in st.session_state:
        st.session_state["app_main_navigation_radio"] = "Dashboard"

    # Sync main nav radio
    selected = st.radio(
        "Navigation",
        PAGE_NAMES,
        format_func=lambda x: f"{PAGE_ICONS.get(x, chr(32))} {x}",
        label_visibility="collapsed",
        key="app_main_navigation_radio",
    )
    st.session_state["active_page"] = selected

    st.markdown("---")
    st.caption("CareerOS v1.1.0 · Placement Edition")

# ── Page Router ───────────────────────────────────────────────
if selected == "Dashboard":
    from src.ui.dashboard import render
    render(db)

elif selected == "My Resumes":
    from src.ui.resume_manager_page import render
    render(db)

elif selected == "Resume Editor":
    from src.ui.resume_editor_page import render
    render(db)

elif selected == "Resume Preview":
    from src.ui.resume_preview import render
    render(db)

elif selected == "Resume Optimization":
    from src.ui.optimization_page import render
    render(db)

elif selected == "Resume Templates":
    from src.ui.resume_templates_page import render
    render(db)

elif selected == "Find Jobs":
    from src.ui.jobs_page import render
    render(db)

elif selected == "Job Matching":
    from src.ui.matching_page import render
    render(db)

elif selected == "Application Tracker":
    from src.ui.tracker_page import render
    render(db)

elif selected == "Automation":
    from src.ui.automation_page import render
    render(db)

elif selected == "API & Extension":
    from src.ui.api_page import render
    render(db)

elif selected == "Settings":
    from src.ui.settings_page import render
    render(db)
