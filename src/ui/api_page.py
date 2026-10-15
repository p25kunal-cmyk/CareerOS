"""CareerOS API Management Page.

Provides controls to start/stop the local FastAPI server,
display the API token, show connection status, and extension
installation instructions.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import streamlit as st

from src.database.connection import DatabaseConnection
from src.ui.components import section_header, metric_card, empty_state
from src.utils.logger import get_logger
from config.settings import settings

logger = get_logger("ui.api_page")

# ── Token path ────────────────────────────────────────────────
TOKEN_FILE = Path(settings.project_root) / "data" / ".api_token"
PID_FILE = Path(settings.project_root) / "data" / ".api_pid"


def _get_api_token() -> str:
    """Read or create the API token."""
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    if TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text().strip()
        if len(token) >= 32:
            return token

    import secrets
    token = secrets.token_hex(32)
    TOKEN_FILE.write_text(token)
    TOKEN_FILE.chmod(0o600)
    return token


def _is_server_running() -> bool:
    """Check if the API server process is alive."""
    if not PID_FILE.exists():
        return False

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)  # Signal 0 = check if process exists
        return True
    except (ProcessLookupError, ValueError, PermissionError):
        PID_FILE.unlink(missing_ok=True)
        return False


def _check_api_health() -> bool:
    """Ping the API health endpoint."""
    try:
        import requests
        resp = requests.get(
            f"http://{settings.api.host}:{settings.api.port}/api/health",
            timeout=2,
        )
        return resp.status_code == 200
    except Exception:
        return False


def _start_server() -> bool:
    """Start the API server as a background subprocess."""
    try:
        proc = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn",
                "src.api.server:create_app",
                "--factory",
                "--host", settings.api.host,
                "--port", str(settings.api.port),
                "--log-level", "info",
            ],
            cwd=str(settings.project_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(proc.pid))
        logger.info("API server started (PID %d) on port %d", proc.pid, settings.api.port)

        # Wait briefly for startup
        time.sleep(1.5)
        return _check_api_health()
    except Exception as e:
        logger.error("Failed to start API server: %s", e)
        return False


def _stop_server() -> bool:
    """Stop the API server process."""
    if not PID_FILE.exists():
        return True

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        time.sleep(0.5)

        # Force kill if still running
        try:
            os.kill(pid, 0)
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

        PID_FILE.unlink(missing_ok=True)
        logger.info("API server stopped (PID %d)", pid)
        return True
    except Exception as e:
        logger.error("Failed to stop API server: %s", e)
        PID_FILE.unlink(missing_ok=True)
        return False


def render(db: DatabaseConnection):
    """Render the API & Extension management page."""
    section_header(
        "⚡ API & Chrome Extension",
        "Manage the local REST API and connect the CareerOS Chrome extension.",
    )

    is_running = _is_server_running()
    is_healthy = _check_api_health() if is_running else False
    api_token = _get_api_token()

    # ── Server Status ─────────────────────────────────────────
    st.markdown("### 🖥️ API Server")

    col1, col2, col3 = st.columns(3)
    with col1:
        if is_healthy:
            metric_card("Status", "Running", icon="🟢")
        elif is_running:
            metric_card("Status", "Starting...", icon="🟡")
        else:
            metric_card("Status", "Stopped", icon="🔴")

    with col2:
        metric_card("Port", str(settings.api.port), icon="🔌")

    with col3:
        metric_card("Host", settings.api.host, icon="🏠")

    st.markdown("")

    # ── Start / Stop Controls ─────────────────────────────────
    col_start, col_stop, col_restart = st.columns(3)

    with col_start:
        if st.button(
            "▶️ Start Server" if not is_running else "✅ Server Running",
            disabled=is_running,
            use_container_width=True,
            type="primary",
        ):
            with st.spinner("Starting API server..."):
                success = _start_server()
                if success:
                    st.success("API server started successfully!")
                    st.rerun()
                else:
                    st.error("Failed to start API server. Check logs.")

    with col_stop:
        if st.button(
            "⏹️ Stop Server",
            disabled=not is_running,
            use_container_width=True,
        ):
            _stop_server()
            st.info("API server stopped.")
            st.rerun()

    with col_restart:
        if st.button(
            "🔄 Restart",
            disabled=not is_running,
            use_container_width=True,
        ):
            with st.spinner("Restarting..."):
                _stop_server()
                time.sleep(1)
                success = _start_server()
                if success:
                    st.success("API server restarted!")
                else:
                    st.error("Restart failed. Check logs.")
            st.rerun()

    st.markdown("---")

    # ── API Token ─────────────────────────────────────────────
    st.markdown("### 🔑 API Token")
    st.caption(
        "This token authenticates the Chrome extension. "
        "Copy it into the extension popup to connect."
    )

    show_token = st.checkbox("Show token", value=False)
    if show_token:
        st.code(api_token, language=None)
    else:
        st.code("●" * 32, language=None)

    col_copy, col_regen = st.columns(2)
    with col_regen:
        if st.button("🔄 Regenerate Token", use_container_width=True):
            import secrets
            new_token = secrets.token_hex(32)
            TOKEN_FILE.write_text(new_token)
            TOKEN_FILE.chmod(0o600)
            st.success("Token regenerated! Update your Chrome extension.")
            st.rerun()

    st.markdown("---")

    # ── API Endpoints Reference ───────────────────────────────
    st.markdown("### 📡 API Endpoints")
    base_url = f"http://{settings.api.host}:{settings.api.port}"

    endpoints = [
        ("GET", "/api/health", "Health check (no auth)", "System"),
        ("GET", "/api/token", "Get API token (localhost only)", "System"),
        ("POST", "/api/jobs", "Save a job", "Jobs"),
        ("GET", "/api/jobs", "List jobs", "Jobs"),
        ("GET", "/api/jobs/{id}", "Get job by ID", "Jobs"),
        ("POST", "/api/jobs/{id}/apply", "Create application", "Applications"),
        ("PUT", "/api/applications/{id}/status", "Update status", "Applications"),
        ("GET", "/api/applications", "List applications", "Applications"),
        ("GET", "/api/resumes", "List resumes", "Resumes"),
        ("GET", "/api/pipeline/stats", "Pipeline stats", "Pipeline"),
        ("POST", "/api/match", "Quick match", "Matching"),
    ]

    for method, path, desc, tag in endpoints:
        method_color = {
            "GET": "#10b981",
            "POST": "#3b82f6",
            "PUT": "#f59e0b",
            "DELETE": "#ef4444",
        }.get(method, "#6b7280")

        st.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;padding:6px 0;'
            f'border-bottom:1px solid #1e293b;">'
            f'<span style="background:{method_color}22;color:{method_color};'
            f'padding:2px 8px;border-radius:4px;font-size:0.75em;font-weight:700;'
            f'font-family:monospace;min-width:48px;text-align:center;">{method}</span>'
            f'<code style="flex:1;font-size:0.85em;color:#e2e8f0;">{path}</code>'
            f'<span style="color:#94a3b8;font-size:0.8em;">{desc}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    if is_healthy:
        st.markdown(f"\n📖 [Open API Documentation]({base_url}/docs)")

    st.markdown("---")

    # ── Chrome Extension Setup ────────────────────────────────
    st.markdown("### 🧩 Chrome Extension Installation")

    extension_dir = Path(settings.project_root) / "extension"
    extension_exists = (extension_dir / "manifest.json").exists()

    if extension_exists:
        st.success(f"Extension files found at `{extension_dir}`")
    else:
        st.warning("Extension files not found!")

    with st.expander("📋 Installation Instructions", expanded=True):
        st.markdown("""
**Step 1: Load the Extension**
1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **Developer mode** (toggle in top-right corner)
3. Click **"Load unpacked"**
4. Select the `extension/` folder inside your CareerOS project

**Step 2: Start the API Server**
1. Click the **▶️ Start Server** button above
2. The server runs on `http://127.0.0.1:8400` (localhost only)

**Step 3: Connect the Extension**
1. Click the CareerOS extension icon in your Chrome toolbar
2. The extension will auto-connect if the API server is running
3. If prompted, paste the API token shown above

**Step 4: Start Saving Jobs!**
1. Browse any supported job board (LinkedIn, Indeed, Naukri, IIMJobs)
2. Open a job posting
3. Click the CareerOS extension icon
4. Job details will be auto-extracted
5. Click **Save Job** — it's added to your CareerOS dashboard!
        """)

    with st.expander("🔧 Supported Job Boards"):
        supported = [
            ("LinkedIn", "linkedin.com/jobs/*", "✅"),
            ("Indeed India", "indeed.com/*, indeed.co.in/*", "✅"),
            ("Naukri", "naukri.com/*", "✅"),
            ("IIMJobs", "iimjobs.com/*", "✅"),
            ("Others", "Any URL — manual entry", "✅"),
        ]
        for name, pattern, status in supported:
            st.markdown(f"- {status} **{name}** — `{pattern}`")

    with st.expander("🔒 Security"):
        st.markdown("""
- The API server **only accepts connections from localhost** (127.0.0.1)
- All endpoints (except `/api/health`) require a **Bearer token**
- The token is stored locally in `data/.api_token` with `chmod 600`
- No data is sent to any external server
- The Chrome extension only communicates with your local machine
        """)
