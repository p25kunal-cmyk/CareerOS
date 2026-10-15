"""Reusable UI components for CareerOS.

Provides metric cards, status badges, empty states, and other shared widgets.
"""

import streamlit as st
from typing import Optional


def metric_card(label: str, value, delta: Optional[str] = None,
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
    <div style="text-align:center;padding:3rem 1rem;color:#6b7280;">
        <div style="font-size:3rem;margin-bottom:0.5rem;">{icon}</div>
        <h3 style="color:#e2e8f0;margin:0 0 0.5rem;">{title}</h3>
        <p style="max-width:400px;margin:0 auto;">{message}</p>
        {action_html}
    </div>
    """, unsafe_allow_html=True)


def section_header(title: str, subtitle: str = ""):
    """Render a page section header."""
    sub_html = f'<p style="color:#94a3b8;margin:0;">{subtitle}</p>' if subtitle else ""
    st.markdown(f"""
    <div style="margin-bottom:1.5rem;">
        <h2 style="color:#f1f5f9;margin:0 0 0.25rem;">{title}</h2>
        {sub_html}
    </div>
    """, unsafe_allow_html=True)


def info_row(label: str, value, inline: bool = True):
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
