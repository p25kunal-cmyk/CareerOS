"""CareerOS Automation, Backup & System Diagnostics UI Page.

Provides controls for automated database backups, scheduled job discovery,
application follow-up reminders, system diagnostics, and background worker state.
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

from config.settings import settings
from src.database.connection import DatabaseConnection
from src.automation.backup import BackupManager
from src.automation.scheduler import AutomationScheduler, AutomationRepository
from src.ui.components import section_header, metric_card, empty_state
from src.utils.logger import get_logger

logger = get_logger("ui.automation_page")


def _get_scheduler(db: DatabaseConnection) -> AutomationScheduler:
    """Retrieve or create singleton scheduler in st.session_state."""
    if "automation_scheduler" not in st.session_state:
        st.session_state.automation_scheduler = AutomationScheduler(db)
    return st.session_state.automation_scheduler


def render(db: DatabaseConnection) -> None:
    """Render the Automation and Maintenance dashboard."""
    section_header(
        "🤖 Automation & System Maintenance",
        "Manage automated database snapshots, background job discovery, reminders, and health diagnostics.",
    )

    scheduler = _get_scheduler(db)
    repo = AutomationRepository(db)
    backup_mgr = BackupManager(db)

    # ── Quick Overview Cards ──────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)

    is_worker_on = scheduler.is_running
    with col1:
        metric_card(
            "Worker Thread",
            "Active" if is_worker_on else "Idle",
            icon="🟢" if is_worker_on else "⚪",
        )

    last_backup = repo.get_recent_run("backup")
    with col2:
        backup_time = (
            datetime.fromisoformat(last_backup["started_at"]).strftime("%b %d, %H:%M")
            if last_backup and last_backup.get("started_at")
            else "Never"
        )
        metric_card("Last Backup", backup_time, icon="💾")

    last_discovery = repo.get_recent_run("job_discovery")
    with col3:
        disco_time = (
            datetime.fromisoformat(last_discovery["started_at"]).strftime("%b %d, %H:%M")
            if last_discovery and last_discovery.get("started_at")
            else "Never"
        )
        metric_card("Last Discovery", disco_time, icon="🔍")

    reminders = scheduler.check_application_reminders()
    with col4:
        metric_card("Due Reminders", str(len(reminders)), icon="⏰")

    st.markdown("")

    # ── Immediate Action Buttons ──────────────────────────────────
    st.markdown("### ⚡ Quick Actions")
    btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)

    with btn_col1:
        if st.button("💾 Backup Now", use_container_width=True, type="primary"):
            with st.spinner("Creating database snapshot..."):
                res = scheduler.execute_backup(label="manual")
                if res["status"] == "success":
                    st.success(f"Backup created: {res['backup_file']}")
                    st.rerun()
                else:
                    st.error(f"Backup failed: {res.get('error')}")

    with btn_col2:
        if st.button("🔍 Run Discovery Now", use_container_width=True):
            with st.spinner("Executing job discovery across sources..."):
                res = scheduler.execute_job_discovery()
                if res["status"] == "success":
                    st.success(res["summary"])
                    st.rerun()
                else:
                    st.error(f"Discovery failed: {res.get('error')}")

    with btn_col3:
        if st.button("🩺 Run Diagnostics", use_container_width=True):
            with st.spinner("Checking database and disk integrity..."):
                diag = scheduler.run_system_diagnostics()
                st.session_state["latest_diagnostics"] = diag

    with btn_col4:
        if not is_worker_on:
            if st.button("▶️ Start Worker", use_container_width=True):
                scheduler.start_background_worker(interval_minutes=60)
                st.success("Background worker started!")
                st.rerun()
        else:
            if st.button("⏹️ Stop Worker", use_container_width=True):
                scheduler.stop_background_worker()
                st.info("Background worker stopped.")
                st.rerun()

    # ── Display Diagnostics if triggered ─────────────────────────
    if "latest_diagnostics" in st.session_state:
        diag = st.session_state["latest_diagnostics"]
        with st.expander("🩺 System Diagnostics Report", expanded=True):
            dcol1, dcol2, dcol3 = st.columns(3)
            with dcol1:
                st.write(f"**Integrity Check:** `{diag['integrity_check']}`")
                st.write(f"**Database Size:** `{diag['db_size_kb']} KB`")
            with dcol2:
                st.write(f"**Free Disk Space:** `{diag['free_disk_gb']} GB`")
                st.write(f"**Status:** `{diag['status'].upper()}`")
            with dcol3:
                st.write(f"**Timestamp:** `{diag['checked_at']}`")

            st.markdown("##### Entity Counts in SQLite")
            cnt_cols = st.columns(len(diag["counts"]))
            for idx, (k, v) in enumerate(diag["counts"].items()):
                with cnt_cols[idx]:
                    st.metric(k.capitalize(), v)

    st.markdown("---")

    # ── Tabbed View ───────────────────────────────────────────────
    tab_reminders, tab_backups, tab_history, tab_settings = st.tabs(
        ["⏰ Application Alerts", "💾 Backups", "📜 Run History", "⚙️ Worker Settings"]
    )

    # ── Tab 1: Application Alerts & Reminders ─────────────────────
    with tab_reminders:
        st.markdown("#### Pending Follow-ups and Stale Applications")
        if not reminders:
            empty_state("No urgent alerts", "All active applications are on schedule.")
        else:
            for r in reminders:
                if r["type"] == "follow_up_due":
                    st.warning(f"⏰ **{r['company']} — {r['job_title']}** (Status: `{r['status']}`)\n\n{r['message']}")
                else:
                    st.info(f"⏳ **{r['company']} — {r['job_title']}** (Status: `{r['status']}`)\n\n{r['message']}")

    # ── Tab 2: Backups Management ─────────────────────────────────
    with tab_backups:
        st.markdown("#### Database Snapshots")
        backups = backup_mgr.list_backups()
        if not backups:
            empty_state("No backups found", "Click 'Backup Now' above to generate your first backup snapshot.")
        else:
            st.caption(f"Found {len(backups)} database snapshot(s) stored locally in `data/backups/`.")
            for b in backups:
                with st.container():
                    bcol1, bcol2, bcol3, bcol4 = st.columns([3, 1.5, 1.5, 2])
                    with bcol1:
                        st.markdown(f"**`{b['filename']}`**")
                    with bcol2:
                        st.text(f"{b['size_kb']} KB")
                    with bcol3:
                        st.text(b["created_at"])
                    with bcol4:
                        if Path(b["path"]).exists():
                            with open(b["path"], "rb") as bf:
                                st.download_button(
                                    label="📥 Download",
                                    data=bf,
                                    file_name=b["filename"],
                                    mime="application/x-sqlite3",
                                    key=f"dl_{b['filename']}",
                                )
                    st.divider()

    # ── Tab 3: Run History ────────────────────────────────────────
    with tab_history:
        st.markdown("#### Task Execution Audit Log")
        runs = repo.list_runs(limit=20)
        if not runs:
            empty_state("No runs logged", "No automated or manual tasks have run yet.")
        else:
            for r in runs:
                status_icon = "🟢" if r["status"] == "completed" else ("🟡" if r["status"] == "running" else "🔴")
                with st.expander(f"{status_icon} **{r['task_type']}** · {r['started_at']} · Status: `{r['status']}`"):
                    st.write(f"**Summary:** {r.get('result_summary') or 'None'}")
                    if r.get("error_message"):
                        st.error(f"**Error:** {r['error_message']}")
                    st.text(f"Processed: {r['items_processed']} | Added: {r['items_added']} | Updated: {r['items_updated']}")
                    if r.get("completed_at"):
                        st.caption(f"Completed at: {r['completed_at']}")

    # ── Tab 4: Worker Settings ────────────────────────────────────
    with tab_settings:
        st.markdown("#### Automation Worker Configuration")
        interval = st.number_input(
            "Worker Interval (Minutes)",
            min_value=5,
            max_value=1440,
            value=60,
            step=5,
            help="How frequently the background worker executes scheduled tasks.",
        )
        retention = st.number_input(
            "Backup Retention Limit",
            min_value=1,
            max_value=50,
            value=10,
            step=1,
            help="Maximum number of historical database backup files to retain.",
        )
        if st.button("💾 Save Automation Settings"):
            with db.transaction() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO user_settings (key, value, category) VALUES ('automation_interval', ?, 'automation')",
                    (str(interval),),
                )
                conn.execute(
                    "INSERT OR REPLACE INTO user_settings (key, value, category) VALUES ('backup_retention', ?, 'automation')",
                    (str(retention),),
                )
            st.success("Automation settings saved!")
