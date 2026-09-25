/**
 * Turbo Download Manager - Popup Control & Developer Diagnostics Logic
 */

document.addEventListener("DOMContentLoaded", async () => {
  const statusBadge = document.getElementById("statusBadge");
  const statusText = document.getElementById("statusText");
  const offlineBanner = document.getElementById("offlineBanner");
  const launchAppBtn = document.getElementById("launchAppBtn");
  const primaryDownloadBtn = document.getElementById("primaryDownloadBtn");
  const primaryDownloadIcon = document.getElementById("primaryDownloadIcon");
  const primaryDownloadText = document.getElementById("primaryDownloadText");
  const winDownloadBtn = document.getElementById("winDownloadBtn");
  const linuxDownloadBtn = document.getElementById("linuxDownloadBtn");

  const urlInput = document.getElementById("urlInput");
  const pasteBtn = document.getElementById("pasteBtn");
  const downloadBtn = document.getElementById("downloadBtn");
  const audioOnlyBtn = document.getElementById("audioOnlyBtn");
  const feedbackMsg = document.getElementById("feedbackMsg");
  const captureCurrentPageBtn = document.getElementById("captureCurrentPageBtn");

  const toggleIntercept = document.getElementById("toggleIntercept");
  const toggleHover = document.getElementById("toggleHover");
  const toggleAutoStart = document.getElementById("toggleAutoStart");
  const toggleDevMode = document.getElementById("toggleDevMode");

  const devSection = document.getElementById("devSection");
  const apiHostInput = document.getElementById("apiHostInput");
  const saveApiHostBtn = document.getElementById("saveApiHostBtn");
  const devLogOutput = document.getElementById("devLogOutput");

  const WIN_MSI_URL = "https://github.com/GashWare/Turbo-Download-Manager/raw/main/MSI/Turbo%20Download%20Manager-2.0.0-win64.msi";
  const LINUX_PKG_URL = "https://github.com/GashWare/Turbo-Download-Manager/raw/main/Distributions/Turbo-Download-Manager-2.0.0-Linux.tar.gz";

  // OS Detection
  function detectOS() {
    const userAgent = navigator.userAgent || "";
    const platform = navigator.platform || "";
    if (/win/i.test(platform) || /windows/i.test(userAgent)) {
      return "windows";
    }
    if (/linux/i.test(platform) || /linux/i.test(userAgent)) {
      return "linux";
    }
    if (/mac/i.test(platform) || /macintosh/i.test(userAgent)) {
      return "mac";
    }
    return "windows"; // default
  }

  const userOS = detectOS();
  if (userOS === "linux") {
    primaryDownloadBtn.href = LINUX_PKG_URL;
    primaryDownloadIcon.textContent = "🐧";
    primaryDownloadText.textContent = "Download for Linux (.tar.gz)";
  } else {
    primaryDownloadBtn.href = WIN_MSI_URL;
    primaryDownloadIcon.textContent = "🪟";
    primaryDownloadText.textContent = "Download for Windows (Installer)";
  }

  // Load saved settings
  const api = typeof browser !== "undefined" ? browser : chrome;
  const config = await api.storage.local.get({
    interceptDownloads: true,
    showVideoOverlay: true,
    autoStartDownloads: true,
    devMode: false,
    apiHost: "http://127.0.0.1:9666"
  });

  toggleIntercept.checked = config.interceptDownloads;
  toggleHover.checked = config.showVideoOverlay;
  toggleAutoStart.checked = config.autoStartDownloads;
  toggleDevMode.checked = config.devMode;
  apiHostInput.value = config.apiHost || "http://127.0.0.1:9666";

  if (config.devMode) {
    devSection.style.display = "block";
  }

  // Toggles event listeners
  toggleIntercept.addEventListener("change", () => {
    api.storage.local.set({ interceptDownloads: toggleIntercept.checked });
  });

  toggleHover.addEventListener("change", () => {
    api.storage.local.set({ showVideoOverlay: toggleHover.checked });
  });

  toggleAutoStart.addEventListener("change", () => {
    api.storage.local.set({ autoStartDownloads: toggleAutoStart.checked });
  });

  toggleDevMode.addEventListener("change", () => {
    const isDev = toggleDevMode.checked;
    devSection.style.display = isDev ? "block" : "none";
    api.storage.local.set({ devMode: isDev });
  });

  // Save custom API Host
  saveApiHostBtn.addEventListener("click", async () => {
    let host = apiHostInput.value.trim() || "http://127.0.0.1:9666";
    if (!host.startsWith("http://") && !host.startsWith("https://")) {
      host = "http://" + host;
    }
    host = host.replace(/\/+$/, "");
    apiHostInput.value = host;
    await api.storage.local.set({ apiHost: host });
    checkAppConnection(true);
  });

  // Check connection to Desktop App
  checkAppConnection();

  statusBadge.addEventListener("click", () => {
    statusBadge.className = "status-badge connecting";
    statusText.textContent = "Checking...";
    checkAppConnection(true);
  });

  function checkAppConnection(isManualCheck = false) {
    api.runtime.sendMessage({ action: "CHECK_CONNECTION" }).then((res) => {
      if (res && res.connected) {
        const ms = res.latencyMs ? ` (${res.latencyMs}ms)` : "";
        statusBadge.className = "status-badge connected";
        statusText.textContent = `Connected${ms}`;
        offlineBanner.style.display = "none";

        if (devLogOutput) {
          devLogOutput.textContent = `[OK] Connected to ${res.statusUrl || "API"}\nLatency: ${res.latencyMs || 0}ms\nActive Tasks: ${res.data?.active_downloads || 0}`;
        }
      } else {
        setOfflineState(res?.error || "Desktop app is offline or not installed", res?.statusUrl);
      }
    }).catch((err) => {
      setOfflineState(err.message);
    });
  }

  function setOfflineState(errMsg, url) {
    statusBadge.className = "status-badge disconnected";
    statusText.textContent = "Software Needed";
    offlineBanner.style.display = "block";

    if (devLogOutput) {
      devLogOutput.textContent = `[OFFLINE] Cannot reach ${url || apiHostInput.value}\nReason: ${errMsg}\nNote: Install or launch Turbo Download Manager Desktop.`;
    }
  }

  // Launch Desktop App via protocol handler
  launchAppBtn.addEventListener("click", () => {
    const protocolUrl = "turbodm://open";
    if (api && api.tabs) {
      api.tabs.create({ url: protocolUrl, active: false }).then((tab) => {
        setTimeout(() => {
          try {
            api.tabs.remove(tab.id);
          } catch (e) {}
          checkAppConnection(true);
        }, 1500);
      }).catch(() => {});
    } else {
      window.location.href = protocolUrl;
    }
    showFeedback("Checking for local Turbo DM...", "success");
  });

  // Paste button
  pasteBtn.addEventListener("click", async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        urlInput.value = text.trim();
        urlInput.focus();
      }
    } catch (e) {
      urlInput.focus();
    }
  });

  // Download Action
  async function triggerDownload(isAudioOnly = false) {
    const url = urlInput.value.trim();
    if (!url) {
      showFeedback("Please enter or paste a valid URL", "error");
      urlInput.focus();
      return;
    }

    showFeedback("Sending to Turbo DM...", "success");

    try {
      const resp = await api.runtime.sendMessage({
        action: "DOWNLOAD_MEDIA",
        url: url,
        audioOnly: isAudioOnly,
        autoStart: toggleAutoStart.checked
      });

      if (resp && resp.success) {
        showFeedback("⚡ Sent to Turbo DM successfully!", "success");
        urlInput.value = "";
      } else {
        showFeedback(resp?.error || "Failed to dispatch download", "error");
      }
    } catch (e) {
      showFeedback("Desktop software required. Please install to continue.", "error");
    }
  }

  downloadBtn.addEventListener("click", () => triggerDownload(false));
  audioOnlyBtn.addEventListener("click", () => triggerDownload(true));

  // Enter key in input
  urlInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      triggerDownload(false);
    }
  });

  // Capture current tab video
  captureCurrentPageBtn.addEventListener("click", async () => {
    if (api && api.tabs) {
      const tabs = await api.tabs.query({ active: true, currentWindow: true });
      if (tabs && tabs[0] && tabs[0].url) {
        urlInput.value = tabs[0].url;
        triggerDownload(false);
      }
    }
  });

  function showFeedback(msg, type) {
    feedbackMsg.textContent = msg;
    feedbackMsg.className = `feedback-msg ${type}`;
    feedbackMsg.style.display = "block";
    setTimeout(() => {
      if (feedbackMsg.textContent === msg) {
        feedbackMsg.style.display = "none";
      }
    }, 4000);
  }
});
