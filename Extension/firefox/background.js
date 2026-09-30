/**
 * Turbo Download Manager - Firefox Background Extension Script
 * Handles browser download interception, context menu triggers, and local IPC to Turbo DM Desktop.
 */

const api = typeof browser !== "undefined" ? browser : (typeof chrome !== "undefined" ? chrome : null);

// Default configuration
const DEFAULT_CONFIG = {
  interceptDownloads: true,
  showVideoOverlay: true,
  autoStartDownloads: true,
  devMode: false,
  apiHost: "http://127.0.0.1:9669",
  minFileSizeMB: 0.1, // Don't intercept tiny tracking pixels/favicons (<100KB)
  excludedExtensions: ["html", "htm", "php", "asp", "aspx", "jsp", "json"]
};

// Initialize settings safely
if (api && api.storage && api.storage.local) {
  try {
    api.storage.local.get(DEFAULT_CONFIG).then((config) => {
      if (config) {
        api.storage.local.set(config);
      }
    }).catch(() => {});
  } catch (e) {}
}

let isAppOnline = false;
let lastHealthCheckTime = 0;
let discoveredHost = "http://127.0.0.1:9669";
const HEALTH_CACHE_TTL_MS = 2500;
const CANDIDATE_HOSTS = ["http://127.0.0.1:9669", "http://127.0.0.1:9666", "http://127.0.0.1:6969", "http://localhost:9669", "http://localhost:9666"];

async function getApiEndpoints() {
  try {
    const config = await (api ? api.storage.local.get({ apiHost: discoveredHost }) : Promise.resolve({}));
    const host = (config && config.apiHost ? config.apiHost : discoveredHost).replace(/\/+$/, "");
    return {
      host: host,
      addUrl: `${host}/add`,
      statusUrl: `${host}/status`
    };
  } catch (e) {
    return {
      host: discoveredHost,
      addUrl: `${discoveredHost}/add`,
      statusUrl: `${discoveredHost}/status`
    };
  }
}

/**
 * Checks if Turbo Download Manager desktop software is running on the local machine.
 * Probes primary host and auto-discovers across candidate ports (9669, 9666, 6969).
 */
async function checkAppHealth(force = false) {
  const now = Date.now();
  if (!force && (now - lastHealthCheckTime < HEALTH_CACHE_TTL_MS)) {
    return isAppOnline;
  }

  const { host, statusUrl } = await getApiEndpoints();
  const hostsToTry = [host, ...CANDIDATE_HOSTS.filter(h => h !== host)];

  for (const h of hostsToTry) {
    try {
      const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
      const timeoutId = controller ? setTimeout(() => controller.abort(), 400) : null;

      const response = await fetch(`${h}/status`, {
        method: "GET",
        cache: "no-store",
        signal: controller ? controller.signal : undefined
      });

      if (timeoutId) clearTimeout(timeoutId);

      if (response.ok) {
        const data = await response.json();
        if (data && (data.status === "ok" || data.connected === true)) {
          isAppOnline = true;
          discoveredHost = h;
          lastHealthCheckTime = Date.now();
          if (api && api.storage && api.storage.local) {
            api.storage.local.set({ apiHost: h }).catch(() => {});
          }
          return true;
        }
      }
    } catch (e) {
      // Continue to next candidate
    }
  }

  isAppOnline = false;
  lastHealthCheckTime = Date.now();
  return false;
}

// Keep connection status warm in background
try {
  checkAppHealth(true).catch(() => {});
  setInterval(() => {
    checkAppHealth(true).catch(() => {});
  }, 5000);
} catch (e) {}

// Setup Context Menus safely
function setupContextMenus() {
  if (!api || !api.contextMenus) return;
  try {
    api.contextMenus.removeAll(() => {
      try {
        api.contextMenus.create({
          id: "turbodm-download-link",
          title: "⚡ Download with Turbo DM",
          contexts: ["link"]
        });

        api.contextMenus.create({
          id: "turbodm-download-media",
          title: "⚡ Download Media with Turbo DM",
          contexts: ["video", "audio", "image"]
        });

        api.contextMenus.create({
          id: "turbodm-download-page",
          title: "⚡ Download Page Video with Turbo DM",
          contexts: ["page"]
        });
      } catch (e) {}
    });
  } catch (e) {}
}

if (api && api.runtime && api.runtime.onInstalled) {
  api.runtime.onInstalled.addListener(setupContextMenus);
}
setupContextMenus();

// Context Menu Click Listener
if (api && api.contextMenus && api.contextMenus.onClicked) {
  api.contextMenus.onClicked.addListener((info, tab) => {
    let targetUrl = "";
    if (info.menuItemId === "turbodm-download-link" && info.linkUrl) {
      targetUrl = info.linkUrl;
    } else if (info.menuItemId === "turbodm-download-media" && info.srcUrl) {
      targetUrl = info.srcUrl;
    } else if (info.menuItemId === "turbodm-download-page" && tab && tab.url) {
      targetUrl = tab.url;
    }

    if (targetUrl) {
      sendDownloadToTurboDM({
        url: targetUrl,
        referrer: tab ? tab.url : "",
        autoStart: true
      });
    }
  });
}

/**
 * Send download request to running Turbo Download Manager instance via HTTP REST API.
 * If app is closed, fallback to launching via turbodm:// protocol handler.
 */
async function sendDownloadToTurboDM(params) {
  const { url, filename, referrer, cookies, autoStart = true, audioOnly = false, formatId = "" } = params;

  if (!url) return { success: false, error: "Empty URL" };

  const payload = JSON.stringify({
    url: url,
    filename: filename || null,
    referrer: referrer || "",
    cookies: cookies || "",
    auto_start: autoStart,
    audio_only: audioOnly,
    format_id: formatId
  });

  const { host } = await getApiEndpoints();
  const hostsToTry = [host, ...CANDIDATE_HOSTS.filter(h => h !== host)];

  for (const h of hostsToTry) {
    try {
      const response = await fetch(`${h}/add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload
      });

      if (response.ok) {
        const data = await response.json();
        discoveredHost = h;
        isAppOnline = true;
        if (api && api.storage && api.storage.local) {
          api.storage.local.set({ apiHost: h }).catch(() => {});
        }
        showNotification("⚡ Turbo Download Manager", `Download queued: ${filename || url.split('/').pop().split('?')[0] || "Media File"}`);
        return { success: true, data };
      }
    } catch (err) {}
  }

  console.warn("[TurboDM] Local API unreachable. Falling back to protocol handler...");
  // Fallback: Launch via turbodm:// deep link
  const protocolUrl = `turbodm://add?url=${encodeURIComponent(url)}`;
  if (api && api.tabs) {
    api.tabs.create({ url: protocolUrl, active: false }).then((tab) => {
      setTimeout(() => {
        try {
          api.tabs.remove(tab.id);
        } catch (e) {}
      }, 1500);
    }).catch(() => {});
  }
  showNotification("⚡ Turbo Download Manager", "Sending download to Turbo DM application...");
  return { success: true, fallback: true };
}

/**
 * Display desktop notification
 */
function showNotification(title, message) {
  try {
    if (api && api.notifications) {
      api.notifications.create({
        type: "basic",
        iconUrl: "icon-48.png",
        title: title,
        message: message
      });
    }
  } catch (e) {
    console.log(`[Notification] ${title}: ${message}`);
  }
}

// Intercept browser downloads
if (api && api.downloads && api.downloads.onCreated) {
  api.downloads.onCreated.addListener(async (downloadItem) => {
    try {
      const config = await api.storage.local.get(DEFAULT_CONFIG);
      if (!config || !config.interceptDownloads) {
        return;
      }

      // Avoid recursive interception or blob URLs or our own desktop installer downloads
      const url = downloadItem.url || "";
      if (!url || url.startsWith("blob:") || url.startsWith("data:") || url.startsWith("about:")) {
        return;
      }
      if (url.includes("GashWare/Turbo-Download-Manager") || url.includes("Turbo%20Download%20Manager") || url.includes("Turbo-Download-Manager")) {
        return;
      }

      // Check file extension exclusion
      const filename = downloadItem.filename ? downloadItem.filename.split(/[\\/]/).pop() : "";
      const ext = filename.split(".").pop().toLowerCase();
      if (ext && config.excludedExtensions && config.excludedExtensions.includes(ext)) {
        return;
      }

      // Check if Turbo Download Manager desktop app is actively running on the system
      const appRunning = await checkAppHealth();
      if (!appRunning) {
        // App is offline / not running: do NOT intercept or cancel the browser's download.
        // Let the native browser download proceed uninterrupted.
        return;
      }

      // Cancel the native browser download and redirect to Turbo DM
      try {
        await api.downloads.cancel(downloadItem.id);
        await api.downloads.erase({ id: downloadItem.id });
      } catch (e) {}

      // Dispatch to Turbo DM
      sendDownloadToTurboDM({
        url: url,
        filename: filename,
        referrer: downloadItem.referrer || "",
        autoStart: config.autoStartDownloads !== undefined ? config.autoStartDownloads : true
      });
    } catch (e) {}
  });
}

// Runtime message dispatcher from content script & popup
if (api && api.runtime && api.runtime.onMessage) {
  api.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "DOWNLOAD_INSTALLER") {
      const osType = request.os || "windows";
      const isLinux = osType === "linux";
      const installerUrl = isLinux
        ? "https://github.com/GashWare/Turbo-Download-Manager/raw/main/Distributions/Turbo-Download-Manager-2.0.0-Linux.tar.gz"
        : "https://github.com/GashWare/Turbo-Download-Manager/raw/main/MSI/Turbo%20Download%20Manager-2.0.0-win64.msi";
      const installerName = isLinux ? "Turbo-Download-Manager-2.0.0-Linux.tar.gz" : "Turbo Download Manager-2.0.0-win64.msi";

      if (api && api.downloads && api.downloads.download) {
        api.downloads.download({
          url: installerUrl,
          filename: installerName,
          saveAs: false,
          conflictAction: "uniquify"
        }).then((id) => {
          showNotification("⚡ Turbo Download Manager", `Downloading installer directly in browser: ${installerName}`);
          sendResponse({ success: true, downloadId: id, filename: installerName });
        }).catch((err) => {
          sendResponse({ success: false, error: err.message, fallbackUrl: installerUrl });
        });
        return true;
      } else {
        sendResponse({ success: false, fallbackUrl: installerUrl });
        return false;
      }
    }

    if (request.action === "DOWNLOAD_MEDIA" || request.action === "SEND_TO_TURBODM") {
      sendDownloadToTurboDM({
        url: request.url,
        filename: request.filename,
        referrer: sender.tab ? sender.tab.url : (request.referrer || ""),
        autoStart: request.autoStart !== undefined ? request.autoStart : true,
        audioOnly: !!request.audioOnly,
        formatId: request.formatId || ""
      }).then((res) => sendResponse(res)).catch((err) => sendResponse({ success: false, error: err.message }));
      return true; // Async response
    }

    if (request.action === "DOWNLOAD_PLAYLIST" || request.action === "DOWNLOAD_BATCH") {
      (async () => {
        const payload = JSON.stringify({
          items: request.items || [],
          subfolder: request.subfolder || "",
          playlist_title: request.playlistTitle || "",
          audio_only: !!request.audioOnly,
          auto_start: true
        });

        const { host } = await getApiEndpoints();
        const hostsToTry = [host, ...CANDIDATE_HOSTS.filter(h => h !== host)];

        for (const h of hostsToTry) {
          try {
            const res = await fetch(`${h}/add`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: payload
            });

            if (res.ok) {
              const data = await res.json();
              discoveredHost = h;
              isAppOnline = true;
              if (api && api.storage && api.storage.local) {
                api.storage.local.set({ apiHost: h }).catch(() => {});
              }
              const count = request.items ? request.items.length : 0;
              showNotification("⚡ Turbo Download Manager", `Queued ${count} tracks from playlist "${request.playlistTitle || 'Playlist'}"`);
              sendResponse({ success: true, count, data });
              return;
            }
          } catch (err) {}
        }

        sendResponse({ success: false, error: "Unable to connect to Turbo Download Manager desktop software" });
      })();
      return true;
    }

    if (request.action === "CHECK_CONNECTION") {
      (async () => {
        const startTime = Date.now();
        const connected = await checkAppHealth(true);
        if (connected) {
          sendResponse({ connected: true, host: discoveredHost, latencyMs: Date.now() - startTime });
        } else {
          sendResponse({ connected: false, error: "Desktop app is not running" });
        }
      })();
      return true;
    }
  });
}
