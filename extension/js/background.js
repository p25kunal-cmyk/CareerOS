/**
 * CareerOS Background Service Worker
 *
 * Handles badge updates and periodic connection checks.
 * Manifest V3 service worker — no persistent background page.
 */

// ── Badge Management ─────────────────────────────────────────

async function updateBadge() {
  try {
    const port = await getStoredPort();
    const resp = await fetch(`http://127.0.0.1:${port}/api/health`, {
      signal: AbortSignal.timeout(3000),
    });

    if (resp.ok) {
      chrome.action.setBadgeBackgroundColor({ color: '#10b981' });
      chrome.action.setBadgeText({ text: '✓' });
    } else {
      setBadgeOffline();
    }
  } catch {
    setBadgeOffline();
  }
}

function setBadgeOffline() {
  chrome.action.setBadgeBackgroundColor({ color: '#6b7280' });
  chrome.action.setBadgeText({ text: '' });
}

async function getStoredPort() {
  // Service workers can't use localStorage, use chrome.storage
  return new Promise((resolve) => {
    chrome.storage.local.get(['careeros_port'], (result) => {
      resolve(result.careeros_port || 8400);
    });
  });
}

// ── Periodic check (every 5 minutes) ─────────────────────────
chrome.alarms.create('healthCheck', { periodInMinutes: 5 });

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'healthCheck') {
    updateBadge();
  }
});

// ── Extension installed ──────────────────────────────────────
chrome.runtime.onInstalled.addListener(() => {
  updateBadge();
});

// Initial check on service worker start
updateBadge();
