"""Reusable UI components for CareerOS.

Provides metric cards, status badges, top navigation breadcrumbs,
empty states, and navigation helpers.
"""

from __future__ import annotations

from typing import Any, Optional
import streamlit as st


def navigate_to(page_name: str, **kwargs):
    """Programmatically and reliably switch to another page."""
    for key, val in kwargs.items():
        st.session_state[key] = val
    st.session_state["active_page"] = page_name
    st.session_state["app_main_navigation_radio"] = page_name
    st.session_state["nav_target"] = page_name
    st.rerun()


def render_top_header(current_page: str, db: Optional[Any] = None):
    """Render a modern top navigation header with breadcrumbs and fast workflow actions."""
    # Determine section category for breadcrumb
    category_map = {
        "Dashboard": "Overview",
        "My Resumes": "Resume Studio",
        "Resume Editor": "Resume Studio",
        "Resume Preview": "Resume Studio",
        "Resume Templates": "Resume Studio",
        "Resume Optimization": "Resume Studio",
        "Find Jobs": "Opportunities",
        "Job Matching": "Opportunities",
        "Application Tracker": "Pipeline",
        "Automation": "Integrations",
        "API & Extension": "Integrations",
        "Settings": "System",
    }
    category = category_map.get(current_page, "Workspace")

    # Get active resume info if db provided
    active_resume_name = "No Resume Loaded"
    if db is not None:
        try:
            from src.resume.repository import ResumeRepository
            repo = ResumeRepository(db)
            resumes = repo.list_resumes()
            if resumes:
                active_id = st.session_state.get("active_resume_id")
                active_res = next((r for r in resumes if r.id == active_id), None) or resumes[0]
                active_resume_name = active_res.name
                if active_res.is_master:
                    active_resume_name = f"⭐ {active_resume_name}"
        except Exception:
            pass

    st.markdown(
        f"""
        <div style="
            background: linear-gradient(90deg, #0f172a 0%, #1e293b 100%);
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 0.65rem 1.25rem;
            margin-bottom: 1.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 4px 20px rgba(0,0,0,0.25);
        ">
            <div style="display:flex; align-items:center; gap:8px;">
                <span style="font-size:1.1rem;">🚀</span>
                <span style="color:#64748b; font-size:0.85rem; font-weight:500;">CareerOS</span>
                <span style="color:#475569; font-size:0.85rem;">/</span>
                <span style="color:#94a3b8; font-size:0.85rem; font-weight:500;">{category}</span>
                <span style="color:#475569; font-size:0.85rem;">/</span>
                <span style="color:#f1f5f9; font-size:0.95rem; font-weight:600;">{current_page}</span>
            </div>
            <div style="display:flex; align-items:center; gap:12px;">
                <div style="background:#0b0f1999; border: 1px solid #334155; padding: 4px 10px; border-radius: 20px; font-size:0.78rem; color:#cbd5e1;">
                    <span style="color:#94a3b8;">Active:</span> <b style="color:#f1f5f9;">{active_resume_name[:24]}</b>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Fast-action quick bar
    quick_cols = st.columns([1, 1, 1, 1, 1, 1, 1])
    pages_bar = [
        ("📊 Dashboard", "Dashboard"),
        ("📄 Resumes", "My Resumes"),
        ("✏️ Editor", "Resume Editor"),
        ("👁️ Preview", "Resume Preview"),
        ("⚡ Optimize", "Resume Optimization"),
        ("🎯 Match", "Job Matching"),
        ("📋 Tracker", "Application Tracker"),
    ]
    for idx, (label, target) in enumerate(pages_bar):
        with quick_cols[idx]:
            is_active = (current_page == target)
            btn_type = "primary" if is_active else "secondary"
            if st.button(label, key=f"top_nav_{target}", type=btn_type, use_container_width=True):
                if not is_active:
                    navigate_to(target)


def metric_card(label: str, value: Any, delta: Optional[str] = None,
                icon: str = "", help_text: str = ""):
    """Render a styled metric card."""
    delta_html = ""
    if delta:
        delta_html = f'<div class="metric-delta">{delta}</div>'

    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-icon">{icon}</div>
        <div class="metric-value">{value}</div>
        <div class="metric-label">{label}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)


def status_badge(status: str) -> str:
    """Return an HTML badge for a given status string."""
    colors = {
        "saved": "#6b7280",
        "shortlisted": "#3b82f6",
        "resume_prepared": "#8b5cf6",
        "applied": "#f59e0b",
        "assessment": "#f97316",
        "interview": "#06b6d4",
        "offer": "#10b981",
        "rejected": "#ef4444",
        "withdrawn": "#9ca3af",
        "active": "#10b981",
        "expired": "#ef4444",
        "closed": "#6b7280",
        "unknown": "#9ca3af",
    }
    color = colors.get(status, "#6b7280")
    label = status.replace("_", " ").title()
    return (
        f'<span style="background:{color}22;color:{color};'
        f'padding:2px 10px;border-radius:12px;font-size:0.82em;'
        f'font-weight:600;border:1px solid {color}44;">{label}</span>'
    )


def empty_state(icon: str, title: str, message: str, action: str = ""):
    """Render a friendly empty-state placeholder."""
    action_html = f'<p style="margin-top:8px;font-size:0.9em">{action}</p>' if action else ""
    st.markdown(f"""
    <div style="text-align:center;padding:3rem 1rem;color:#6b7280;background:#1e293b44;border-radius:12px;border:1px dashed #334155;">
        <div style="font-size:3rem;margin-bottom:0.5rem;">{icon}</div>
        <h3 style="color:#e2e8f0;margin:0 0 0.5rem;">{title}</h3>
        <p style="max-width:400px;margin:0 auto;color:#94a3b8;">{message}</p>
        {action_html}
    </div>
    """, unsafe_allow_html=True)


def section_header(title: str, subtitle: str = ""):
    """Render a page section header."""
    sub_html = f'<p style="color:#94a3b8;margin:0;font-size:0.92rem;">{subtitle}</p>' if subtitle else ""
    st.markdown(f"""
    <div style="margin-bottom:1.25rem;">
        <h2 style="color:#f1f5f9;margin:0 0 0.25rem;font-weight:700;letter-spacing:-0.01em;">{title}</h2>
        {sub_html}
    </div>
    """, unsafe_allow_html=True)


def info_row(label: str, value: Any, inline: bool = True):
    """Render a label-value info row."""
    if inline:
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;'
            f'padding:6px 0;border-bottom:1px solid #1e293b;">'
            f'<span style="color:#94a3b8;">{label}</span>'
            f'<span style="color:#e2e8f0;font-weight:500;">{value}</span></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(f"**{label}:** {value}")


def coming_soon(page_name: str, phase: str):
    """Standard placeholder for pages not yet implemented."""
    empty_state(
        "🚧",
        f"{page_name}",
        f"This module will be implemented in {phase}.",
        "The foundation is ready — building this next.",
    )
