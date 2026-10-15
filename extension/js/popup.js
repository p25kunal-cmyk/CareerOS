/**
 * CareerOS Chrome Extension — Popup Controller
 *
 * Handles API communication, job saving, pipeline display,
 * and auto-extraction of job data from the current tab URL.
 */

// ── Constants ────────────────────────────────────────────────
const DEFAULT_PORT = 8400;
const API_BASE = () => `http://127.0.0.1:${getPort()}`;

// ── State ────────────────────────────────────────────────────
let isConnected = false;

// ── DOM Refs ─────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ── Storage Helpers ──────────────────────────────────────────
function getPort() {
  return localStorage.getItem('careeros_port') || DEFAULT_PORT;
}

function getToken() {
  return localStorage.getItem('careeros_token') || '';
}

function saveConfig(port, token) {
  localStorage.setItem('careeros_port', port);
  localStorage.setItem('careeros_token', token);
}

// ── API Client ───────────────────────────────────────────────
async function apiRequest(path, options = {}) {
  const url = `${API_BASE()}${path}`;
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  const token = getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  try {
    const resp = await fetch(url, {
      ...options,
      headers,
    });

    if (!resp.ok) {
      const errorBody = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(errorBody.detail || `HTTP ${resp.status}`);
    }

    return await resp.json();
  } catch (err) {
    if (err.message.includes('Failed to fetch') || err.message.includes('NetworkError')) {
      throw new Error('Cannot connect to CareerOS. Is the API server running?');
    }
    throw err;
  }
}

// ── Connection Check ─────────────────────────────────────────
async function checkConnection() {
  try {
    const data = await apiRequest('/api/health');
    if (data.status === 'ok') {
      setConnected(true);
      return true;
    }
  } catch {
    // Not connected
  }
  setConnected(false);
  return false;
}

function setConnected(connected) {
  isConnected = connected;
  const badge = $('#connection-badge');
  const setup = $('#setup-panel');
  const main = $('#main-content');

  if (connected) {
    badge.className = 'badge badge--online';
    badge.querySelector('.badge-text').textContent = 'Connected';
    setup.style.display = 'none';
    main.style.display = 'block';
  } else {
    badge.className = 'badge badge--offline';
    badge.querySelector('.badge-text').textContent = 'Offline';
    setup.style.display = 'block';
    main.style.display = 'none';
  }
}

// ── Auto-fill from current tab ───────────────────────────────
async function autoFillFromTab() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab && tab.url) {
      $('#job-url').value = tab.url;

      // Try to extract info from content script
      try {
        const response = await chrome.tabs.sendMessage(tab.id, { action: 'extractJobData' });
        if (response && response.title) {
          $('#job-title').value = response.title || '';
          $('#job-company').value = response.company || '';
          if (response.location) $('#job-location').value = response.location;
          if (response.skills) $('#job-skills').value = response.skills;

          // Detect source portal
          if (tab.url.includes('linkedin.com')) {
            response.source = 'linkedin';
          } else if (tab.url.includes('indeed.com') || tab.url.includes('indeed.co.in')) {
            response.source = 'indeed';
          } else if (tab.url.includes('naukri.com')) {
            response.source = 'naukri';
          } else if (tab.url.includes('iimjobs.com')) {
            response.source = 'iimjobs';
          }
        }
      } catch {
        // Content script not available on this page — that's fine
      }
    }
  } catch {
    // Can't access tab info
  }
}

// ── Save Job ─────────────────────────────────────────────────
async function saveJob() {
  const title = $('#job-title').value.trim();
  const company = $('#job-company').value.trim();

  if (!title || !company) {
    showFeedback('Title and Company are required.', 'error');
    return;
  }

  const skills = $('#job-skills').value
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);

  const url = $('#job-url').value.trim();
  let sourcePortal = 'chrome_extension';
  if (url.includes('linkedin.com')) sourcePortal = 'linkedin';
  else if (url.includes('indeed.com') || url.includes('indeed.co.in')) sourcePortal = 'indeed';
  else if (url.includes('naukri.com')) sourcePortal = 'naukri';
  else if (url.includes('iimjobs.com')) sourcePortal = 'iimjobs';

  const payload = {
    title,
    company,
    location: $('#job-location').value.trim() || null,
    employment_type: $('#job-type').value,
    required_skills: skills,
    source_portal: sourcePortal,
    original_url: url || null,
  };

  const btn = $('#btn-save-job');
  btn.disabled = true;
  btn.innerHTML = '<span class="btn-icon">⏳</span> Saving...';

  try {
    const result = await apiRequest('/api/jobs', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    if (result.created) {
      showFeedback('✅ Job saved to CareerOS!', 'success');
      showToast('Job saved successfully!', 'success');
      // Clear form
      $('#job-title').value = '';
      $('#job-company').value = '';
      $('#job-location').value = '';
      $('#job-skills').value = '';
    } else {
      showFeedback('⚠️ This job already exists in CareerOS.', 'duplicate');
    }

    // Refresh lists
    loadRecentJobs();
    loadPipelineStats();
  } catch (err) {
    showFeedback(`❌ ${err.message}`, 'error');
    showToast(err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span class="btn-icon">💾</span> Save Job';
  }
}

// ── Pipeline Stats ───────────────────────────────────────────
async function loadPipelineStats() {
  const container = $('#pipeline-stats');
  try {
    const data = await apiRequest('/api/pipeline/stats');

    const stageConfig = [
      { key: 'saved', label: 'Saved', cls: '' },
      { key: 'shortlisted', label: 'Shortlist', cls: '' },
      { key: 'applied', label: 'Applied', cls: 'pipeline-stage--applied' },
      { key: 'interview', label: 'Interview', cls: 'pipeline-stage--active' },
      { key: 'offer', label: 'Offers', cls: 'pipeline-stage--offer' },
      { key: 'rejected', label: 'Rejected', cls: '' },
    ];

    container.innerHTML = `
      <div class="pipeline-grid">
        ${stageConfig
          .map(
            (s) => `
          <div class="pipeline-stage ${s.cls}">
            <div class="pipeline-count">${data.stages[s.key] || 0}</div>
            <div class="pipeline-label">${s.label}</div>
          </div>
        `
          )
          .join('')}
      </div>
    `;
  } catch {
    container.innerHTML = '<div class="pipeline-loading">Unable to load pipeline</div>';
  }
}

// ── Recent Jobs ──────────────────────────────────────────────
async function loadRecentJobs() {
  const container = $('#recent-jobs');
  try {
    const data = await apiRequest('/api/jobs?limit=5');

    if (!data.jobs || data.jobs.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">📭</div>
          <div>No jobs saved yet. Start by saving one above!</div>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <ul class="job-list">
        ${data.jobs
          .map(
            (job) => `
          <li class="job-item">
            <div class="job-avatar">${job.company.charAt(0).toUpperCase()}</div>
            <div class="job-info">
              <div class="job-title">${escapeHtml(job.title)}</div>
              <div class="job-company">${escapeHtml(job.company)}${job.location ? ' · ' + escapeHtml(job.location) : ''}</div>
            </div>
            <span class="job-source">${job.source_portal}</span>
          </li>
        `
          )
          .join('')}
      </ul>
    `;
  } catch {
    container.innerHTML = '<div class="pipeline-loading">Unable to load jobs</div>';
  }
}

// ── UI Helpers ───────────────────────────────────────────────
function showFeedback(message, type) {
  const el = $('#save-feedback');
  el.textContent = message;
  el.className = `feedback feedback--${type}`;
  el.style.display = 'block';
  setTimeout(() => {
    el.style.display = 'none';
  }, 4000);
}

function showToast(message, type = 'success') {
  const container = $('#toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast--${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ── Event Handlers ───────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  // Check for saved config
  const token = getToken();
  if (token) {
    const connected = await checkConnection();
    if (connected) {
      autoFillFromTab();
      loadPipelineStats();
      loadRecentJobs();
      return;
    }
  }

  // Show setup
  setConnected(false);

  // Try auto-connect (fetch token from API)
  try {
    const resp = await fetch(`http://127.0.0.1:${getPort()}/api/token`);
    if (resp.ok) {
      const data = await resp.json();
      saveConfig(data.port || DEFAULT_PORT, data.token);
      const connected = await checkConnection();
      if (connected) {
        autoFillFromTab();
        loadPipelineStats();
        loadRecentJobs();
      }
    }
  } catch {
    // API not running
  }
});

// Connect button
$('#btn-connect')?.addEventListener('click', async () => {
  const port = $('#api-port').value || DEFAULT_PORT;
  const token = $('#api-token').value.trim();

  if (!token) {
    showToast('Please enter the API token', 'error');
    return;
  }

  saveConfig(port, token);
  const connected = await checkConnection();
  if (connected) {
    showToast('Connected to CareerOS!', 'success');
    autoFillFromTab();
    loadPipelineStats();
    loadRecentJobs();
  } else {
    showToast('Connection failed. Check port and token.', 'error');
  }
});

// Save job button
$('#btn-save-job')?.addEventListener('click', saveJob);

// Refresh stats
$('#btn-refresh-stats')?.addEventListener('click', () => {
  loadPipelineStats();
  loadRecentJobs();
});

// Enter key on form fields
$$('#job-title, #job-company').forEach((input) => {
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') saveJob();
  });
});
