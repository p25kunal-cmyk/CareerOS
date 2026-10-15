"""CareerOS Settings page — AI configuration, matching weights, and system info."""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from config.settings import settings
from src.database.connection import DatabaseConnection
from src.ui.components import section_header, metric_card
from src.utils.logger import get_logger

logger = get_logger("ui.settings")


def render(db: DatabaseConnection):
    """Render the Settings & AI Usage page."""
    section_header("Settings & AI Usage", "Configure your CareerOS instance, AI keys, and matching algorithms.")

    tabs = st.tabs(["🤖 AI Provider", "🎯 Matching Weights", "💾 Data & Backup", "ℹ️ System Info"])

    with tabs[0]:
        _render_ai_settings(db)

    with tabs[1]:
        _render_matching_weights(db)

    with tabs[2]:
        _render_data_settings(db)

    with tabs[3]:
        _render_system_info(db)


def _render_ai_settings(db: DatabaseConnection):
    """AI provider configuration panel with interactive setup."""
    st.markdown("#### AI Provider Configuration")

    # Fetch stored settings from DB
    cur_provider_row = db.execute_one("SELECT value FROM user_settings WHERE key = 'ai_provider'")
    cur_key_row = db.execute_one("SELECT value FROM user_settings WHERE key = 'ai_api_key'")
    cur_model_row = db.execute_one("SELECT value FROM user_settings WHERE key = 'ai_model'")
    cur_budget_row = db.execute_one("SELECT value FROM user_settings WHERE key = 'ai_monthly_budget'")

    current_provider = (cur_provider_row["value"] if cur_provider_row else "") or settings.ai.provider or "google"
    current_key = (cur_key_row["value"] if cur_key_row else "") or settings.ai.api_key or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    current_model = (cur_model_row["value"] if cur_model_row else "") or settings.ai.model or "gemini-1.5-flash"
    current_budget = float(cur_budget_row["value"]) if cur_budget_row else getattr(settings.ai, "monthly_budget", 10.0)

    is_configured = bool(current_key and len(current_key) > 5)

    if is_configured:
        st.success(f"✅ AI Active — **{current_provider.upper()}** (`{current_model}`)")
    else:
        st.info("💡 **Rule-Based Offline Mode Active**. To enable live cloud AI suggestions, configure your API key below. All features work completely fine without an API key.")

    with st.form("ai_config_form"):
        col1, col2 = st.columns(2)
        with col1:
            provider_choice = st.selectbox(
                "AI Provider",
                options=["Google Gemini (Recommended - Generous Free Tier)", "OpenAI", "Offline (Rule-Based Only)"],
                index=0 if current_provider in ("google", "gemini") else (1 if current_provider == "openai" else 2),
                help="Google Gemini offers 15 free requests per minute with no credit card required.",
            )

        with col2:
            if "Gemini" in provider_choice:
                model_options = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"]
            elif "OpenAI" in provider_choice:
                model_options = ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]
            else:
                model_options = ["rules-engine-v1"]

            model_choice = st.selectbox(
                "Model",
                options=model_options,
                index=0 if current_model not in model_options else model_options.index(current_model),
            )

        api_key_input = st.text_input(
            "API Key",
            value=current_key if "Offline" not in provider_choice else "",
            type="password",
            placeholder="AIzaSy... (Gemini) or sk-... (OpenAI)",
            help="Your API key is stored securely in your local SQLite database and never leaves your computer.",
        )

        col3, col4 = st.columns(2)
        with col3:
            budget_input = st.number_input(
                "Monthly Budget Limit ($ USD)",
                min_value=1.0,
                max_value=100.0,
                value=float(current_budget),
                step=1.0,
                help="Hard spending limit. AI requests will automatically stop when this cap is reached.",
            )
        with col4:
            st.markdown("<br>", unsafe_allow_html=True)
            submitted = st.form_submit_button("💾 Save AI Settings", use_container_width=True, type="primary")

        if submitted:
            norm_provider = "google" if "Gemini" in provider_choice else ("openai" if "OpenAI" in provider_choice else "offline")
            with db.transaction() as conn:
                conn.execute("INSERT OR REPLACE INTO user_settings (key, value, category) VALUES ('ai_provider', ?, 'ai')", (norm_provider,))
                conn.execute("INSERT OR REPLACE INTO user_settings (key, value, category) VALUES ('ai_api_key', ?, 'ai')", (api_key_input.strip(),))
                conn.execute("INSERT OR REPLACE INTO user_settings (key, value, category) VALUES ('ai_model', ?, 'ai')", (model_choice,))
                conn.execute("INSERT OR REPLACE INTO user_settings (key, value, category) VALUES ('ai_monthly_budget', ?, 'ai')", (str(budget_input),))

            settings.ai.provider = norm_provider
            settings.ai.api_key = api_key_input.strip()
            settings.ai.model = model_choice
            settings.ai.monthly_budget = budget_input

            st.success("✅ AI settings saved successfully!")
            st.rerun()

    # Test Connection Button
    if is_configured:
        if st.button("🧪 Test AI Connection"):
            with st.spinner("Testing connection with AI provider..."):
                try:
                    from src.ai.provider import get_ai_provider
                    ai = get_ai_provider(db)
                    resp, tin, tout, cost = ai.generate("Rephrase: Managed marketing campaigns for university festival.", temperature=0.5)
                    st.success(f"Connection Successful! Model: `{ai.model}` (Tokens in: {tin}, Tokens out: {tout})")
                    st.json(resp)
                except Exception as e:
                    st.error(f"Connection Failed: {e}")

    st.markdown("---")

    # AI usage summary
    st.markdown("#### 📊 AI Token & Budget Usage This Month")
    usage = db.execute(
        """SELECT COUNT(*) as calls,
                  SUM(CASE WHEN cache_hit=1 THEN 1 ELSE 0 END) as cache_hits,
                  SUM(input_tokens) as total_input,
                  SUM(output_tokens) as total_output,
                  SUM(estimated_cost) as total_cost
           FROM ai_usage_records
           WHERE created_at >= date('now', 'start of month')"""
    )
    if usage and usage[0]["calls"]:
        row = usage[0]
        cols = st.columns(4)
        cols[0].metric("API Calls", row["calls"])
        cols[1].metric("Cache Hits", row["cache_hits"] or 0)
        cols[2].metric("Tokens Used", f"{(row['total_input'] or 0) + (row['total_output'] or 0):,}")
        cols[3].metric("Est. Cost", f"${row['total_cost'] or 0:.4f}")

        remaining = current_budget - (row["total_cost"] or 0)
        if remaining <= 0:
            st.error("🚫 Monthly budget exhausted. AI calls are disabled until next month.")
        elif remaining < current_budget * 0.2:
            st.warning(f"⚠️ Budget remaining: ${remaining:.4f}")
    else:
        st.info("No billable AI usage recorded this month.")


def _render_matching_weights(db: DatabaseConnection):
    """Allow users to adjust job matching score weights."""
    st.markdown("#### Matching Score Weights")
    st.caption("Adjust how different factors contribute to the job match score (total should be 100).")

    weights = {}
    rows = db.execute(
        "SELECT key, value FROM user_settings WHERE category = 'matching' ORDER BY key"
    )
    for r in rows:
        weights[r["key"]] = float(r["value"])

    labels = {
        "matching_weight_required_skills": ("Required Skills Match", 30),
        "matching_weight_preferred_skills": ("Preferred Skills Match", 15),
        "matching_weight_experience_level": ("Experience Level Match", 15),
        "matching_weight_role_alignment": ("Role Title Alignment", 20),
        "matching_weight_domain_relevance": ("Domain Relevance", 10),
        "matching_weight_location_preference": ("Location Preference", 10),
    }

    cols = st.columns(2)
    new_weights = {}
    idx = 0
    for key, (label, default_val) in labels.items():
        col = cols[idx % 2]
        current_val = int(weights.get(key, default_val))
        new_val = col.slider(label, 0, 50, current_val, key=f"mw_{key}")
        new_weights[key] = new_val
        idx += 1

    total = sum(new_weights.values())
    if total != 100:
        st.warning(f"⚠️ Total weight is **{total}%** (should equal 100%)")
    else:
        st.success("✅ Weights sum to 100%")

    if st.button("Save Weights", type="primary"):
        with db.transaction() as conn:
            for k, v in new_weights.items():
                conn.execute(
                    "INSERT OR REPLACE INTO user_settings (key, value, category) VALUES (?, ?, 'matching')",
                    (k, str(v)),
                )
        st.success("Matching weights updated.")


def _render_data_settings(db: DatabaseConnection):
    """Data management and export controls."""
    st.markdown("#### Database Maintenance")

    db_path = Path(settings.database.path)
    if db_path.exists():
        size_kb = db_path.stat().st_size / 1024
        st.info(f"Database location: `{db_path}` ({size_kb:.1f} KB)")
    else:
        st.warning(f"Database not found at `{db_path}`")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🧹 Clean Stale Matches"):
            from src.matching.engine import MatchingEngine
            engine = MatchingEngine(db)
            cleaned = engine.invalidate_stale_matches()
            st.success(f"Cleared {cleaned} stale match scores.")

    with col2:
        if st.button("🗑️ Clear AI Cache"):
            with db.transaction() as conn:
                conn.execute("DELETE FROM ai_cache")
            st.success("AI prompt cache cleared.")


def _render_system_info(db: DatabaseConnection):
    """Display environment details, paths, and version info."""
    st.markdown("#### System Information")

    info_row("CareerOS Version", "1.0.0 (Production Ready)")
    info_row("Project Root", str(settings.project_root))
    info_row("Data Directory", settings.data_dir)
    info_row("Database Path", settings.database.path)
    info_row("Uploads Directory", settings.uploads_dir)
    info_row("Backups Directory", settings.backups_dir)
    info_row("Log File", settings.logging.log_file)
    info_row("Log Level", settings.logging.level)


def info_row(label: str, value: str):
    """Helper to display a clean key-value row."""
    st.markdown(
        f'<div style="display:flex; justify-content:space-between; padding: 6px 0; border-bottom: 1px solid #1e293b;">'
        f'<span style="color:#94a3b8; font-size:0.9rem;">{label}</span>'
        f'<span style="color:#e2e8f0; font-family:monospace; font-size:0.85rem;">{value}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
