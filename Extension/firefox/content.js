/**
 * Turbo Download Manager - Ultra-Lightweight & Robust Video Hover Overlay Script
 * Injects a floating "⚡ Download with Download Manager" button over any video on any website.
 * Designed for high performance with zero-lag global event delegation.
 */

(function () {
  "use strict";

  // Prevent multiple injections
  if (window.__TURBODM_CONTENT_INITIALIZED__) return;
  window.__TURBODM_CONTENT_INITIALIZED__ = true;

  const api = typeof browser !== "undefined" ? browser : (typeof chrome !== "undefined" ? chrome : null);
  let overlayBtn = null;
  let activeTarget = null;
  let hideTimer = null;
  let isOverlayEnabled = true;
  let lastMoveTime = 0;

  // Load user configuration
  if (api && api.storage && api.storage.local) {
    try {
      api.storage.local.get({ showVideoOverlay: true }).then((cfg) => {
        isOverlayEnabled = cfg ? cfg.showVideoOverlay : true;
      }).catch(() => {});
    } catch (e) {}
  }

  /**
   * Safely sets overlay button content using DOM APIs (Zero innerHTML).
   */
  function setButtonContent(btn, iconText, labelText, showAudioOpt = true) {
    while (btn.firstChild) {
      btn.removeChild(btn.firstChild);
    }

    const iconSpan = document.createElement("span");
    iconSpan.className = "turbodm-icon";
    iconSpan.style.pointerEvents = "none";
    iconSpan.textContent = iconText;
    btn.appendChild(iconSpan);

    const textSpan = document.createElement("span");
    textSpan.className = "turbodm-text";
    textSpan.style.pointerEvents = "none";
    textSpan.textContent = labelText;
    btn.appendChild(textSpan);

    if (showAudioOpt) {
      const audioSpan = document.createElement("span");
      audioSpan.className = "turbodm-audio-opt";
      audioSpan.title = "Download Audio Only (MP3)";
      audioSpan.textContent = "MP3";
      btn.appendChild(audioSpan);
    }
  }

  function resetOverlayButtonState(btn) {
    btn.classList.remove("turbodm-success");
    setButtonContent(btn, "⚡", "Download with Turbo DM", true);
  }

  /**
   * Lazily creates the single shared overlay button DOM node.
   */
  function getOrCreateOverlayButton() {
    if (overlayBtn && overlayBtn.parentNode) {
      return overlayBtn;
    }

    overlayBtn = document.createElement("div");
    overlayBtn.id = "turbodm-floating-overlay";
    overlayBtn.className = "turbodm-video-overlay-btn";
    setButtonContent(overlayBtn, "⚡", "Download with Turbo DM", true);

    // Click handler with error handling
    overlayBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      e.preventDefault();
      const isAudioOnly = e.target && e.target.classList.contains("turbodm-audio-opt");
      triggerDownload(activeTarget, isAudioOnly);
    });

    // Keep visible when mouse enters the button
    overlayBtn.addEventListener("mouseenter", () => {
      if (hideTimer) {
        clearTimeout(hideTimer);
        hideTimer = null;
      }
      overlayBtn.classList.add("turbodm-visible");
    });

    // Schedule hide when mouse leaves the button
    overlayBtn.addEventListener("mouseleave", () => {
      scheduleHide(500);
    });

    return overlayBtn;
  }

  /**
   * Mounts the overlay button to the right container (fullscreen element or document.body).
   */
  function mountButton(btn) {
    const parentContainer = document.fullscreenElement || document.webkitFullscreenElement || document.body;
    if (parentContainer && btn.parentNode !== parentContainer) {
      try {
        parentContainer.appendChild(btn);
      } catch (e) {
        document.documentElement.appendChild(btn);
      }
    }
  }

  /**
   * Extracts the best video or page URL to download.
   */
  function resolveTargetUrl(targetEl) {
    const pageUrl = window.location.href;
    const hostname = window.location.hostname.toLowerCase();

    // 1. YouTube specific resolution
    if (hostname.includes("youtube.com") || hostname.includes("youtu.be")) {
      // If hovering over a feed card (home, subscriptions, search, channel page)
      if (targetEl) {
        const cardContainer = targetEl.closest("ytd-rich-grid-media, ytd-video-renderer, ytd-grid-video-renderer, ytd-compact-video-renderer, ytd-reel-item-renderer, ytd-rich-item-renderer");
        if (cardContainer) {
          const link = cardContainer.querySelector("a#video-title-link, a#thumbnail, a.ytd-thumbnail");
          if (link && link.href && !link.href.includes("/shorts/")) {
            return link.href;
          }
        }
      }
      return pageUrl;
    }

    // 2. Twitter / X resolution
    if (hostname.includes("twitter.com") || hostname.includes("x.com")) {
      if (targetEl) {
        const tweet = targetEl.closest("article");
        if (tweet) {
          const timeLink = tweet.querySelector("time")?.parentElement;
          if (timeLink && timeLink.href) return timeLink.href;
        }
      }
      return pageUrl;
    }

    // 3. Instagram resolution
    if (hostname.includes("instagram.com")) {
      if (targetEl) {
        const post = targetEl.closest("article") || targetEl.closest("div[role='dialog']");
        if (post) {
          const postLink = post.querySelector("a[href*='/p/'], a[href*='/reel/']");
          if (postLink && postLink.href) return postLink.href;
        }
      }
      return pageUrl;
    }

    // 4. Facebook resolution
    if (hostname.includes("facebook.com")) {
      if (targetEl) {
        const post = targetEl.closest("div[role='article']") || targetEl.closest("div[role='feed']");
        if (post) {
          const fbLink = post.querySelector("a[href*='/watch'], a[href*='/reel/'], a[href*='/videos/']");
          if (fbLink && fbLink.href) return fbLink.href;
        }
      }
      return pageUrl;
    }

    // 5. Twitch resolution (Clips, VODs, Highlights, Channel streams)
    if (hostname.includes("twitch.tv")) {
      if (targetEl) {
        const card = targetEl.closest("article, div[data-target], .tw-card, div[data-a-target*='card']");
        if (card) {
          const clipLink = card.querySelector("a[href*='/clip/'], a[href*='/videos/'], a[data-a-target*='link']");
          if (clipLink && clipLink.href) return clipLink.href;
        }
      }
      return pageUrl;
    }

    // 6. TikTok / Reddit / Vimeo / Dailymotion
    if (hostname.includes("tiktok.com") || hostname.includes("reddit.com") || hostname.includes("vimeo.com") || hostname.includes("dailymotion.com")) {
      return pageUrl;
    }

    // 6. Direct HTML5 Video element source resolution
    if (targetEl) {
      const videoEl = targetEl.tagName === "VIDEO" ? targetEl : targetEl.querySelector("video");
      if (videoEl) {
        if (videoEl.currentSrc && !videoEl.currentSrc.startsWith("blob:") && !videoEl.currentSrc.startsWith("data:")) {
          return videoEl.currentSrc;
        }
        if (videoEl.src && !videoEl.src.startsWith("blob:") && !videoEl.src.startsWith("data:")) {
          return videoEl.src;
        }
        const source = videoEl.querySelector("source[src]");
        if (source && source.src && !source.src.startsWith("blob:")) {
          return source.src;
        }
      }
    }

    return pageUrl;
  }

  /**
   * Spawns a sleek modal prompt when desktop software is required / not found.
   */
  function showAppRequiredModal() {
    let modal = document.getElementById("turbodm-app-required-modal");
    if (!modal) {
      modal = document.createElement("div");
      modal.id = "turbodm-app-required-modal";
      modal.className = "turbodm-modal-overlay";

      const isLinux = /linux/i.test(navigator.platform || "") || /linux/i.test(navigator.userAgent || "");
      const primaryUrl = isLinux
        ? "https://github.com/GashWare/Turbo-Download-Manager/raw/main/Distributions/Turbo-Download-Manager-2.0.0-Linux.tar.gz"
        : "https://github.com/GashWare/Turbo-Download-Manager/raw/main/MSI/Turbo%20Download%20Manager-2.0.0-win64.msi";
      const primaryLabel = isLinux ? "🐧 Download for Linux (.tar.gz)" : "🪟 Download for Windows (.msi)";

      const card = document.createElement("div");
      card.className = "turbodm-modal-card";

      const header = document.createElement("div");
      header.className = "turbodm-modal-header";

      const title = document.createElement("div");
      title.className = "turbodm-modal-title";
      title.textContent = "⚡ Turbo Download Manager Desktop Required";

      const closeBtn = document.createElement("button");
      closeBtn.className = "turbodm-modal-close";
      closeBtn.id = "turbodmModalClose";
      closeBtn.textContent = "✕";

      header.appendChild(title);
      header.appendChild(closeBtn);

      const desc = document.createElement("p");
      desc.className = "turbodm-modal-desc";
      desc.textContent = "To download and capture video streams at maximum accelerated speeds, the Turbo Download Manager desktop software is required.";

      const actions = document.createElement("div");
      actions.className = "turbodm-modal-actions";

      const primaryBtn = document.createElement("a");
      primaryBtn.href = primaryUrl;
      primaryBtn.target = "_blank";
      primaryBtn.className = "turbodm-modal-btn primary";
      primaryBtn.textContent = primaryLabel;
      actions.appendChild(primaryBtn);

      const grid = document.createElement("div");
      grid.className = "turbodm-modal-grid";

      const winBtn = document.createElement("a");
      winBtn.href = "https://github.com/GashWare/Turbo-Download-Manager/raw/main/MSI/Turbo%20Download%20Manager-2.0.0-win64.msi";
      winBtn.target = "_blank";
      winBtn.className = "turbodm-modal-btn secondary";
      winBtn.textContent = "🪟 Windows Installer";

      const linuxBtn = document.createElement("a");
      linuxBtn.href = "https://github.com/GashWare/Turbo-Download-Manager/raw/main/Distributions/Turbo-Download-Manager-2.0.0-Linux.tar.gz";
      linuxBtn.target = "_blank";
      linuxBtn.className = "turbodm-modal-btn secondary";
      linuxBtn.textContent = "🐧 Linux Package";

      grid.appendChild(winBtn);
      grid.appendChild(linuxBtn);
      actions.appendChild(grid);

      const docLink = document.createElement("a");
      docLink.href = "https://github.com/GashWare/Turbo-Download-Manager";
      docLink.target = "_blank";
      docLink.className = "turbodm-modal-link";
      docLink.textContent = "📦 View on GitHub Releases & Documentation";
      actions.appendChild(docLink);

      function triggerDirectInstallerDownload(e, osType, btnEl) {
        if (api && api.runtime && api.runtime.sendMessage) {
          e.preventDefault();
          const origText = btnEl.textContent;
          btnEl.textContent = "⏳ Downloading in Browser...";
          api.runtime.sendMessage({ action: "DOWNLOAD_INSTALLER", os: osType }).then((resp) => {
            if (resp && resp.success) {
              btnEl.textContent = "✓ Downloading! Click Firefox Downloads Bar to Run";
              setTimeout(() => {
                btnEl.textContent = origText;
              }, 4000);
            } else if (resp && resp.fallbackUrl) {
              window.open(resp.fallbackUrl, "_blank");
              btnEl.textContent = origText;
            }
          }).catch(() => {
            window.open(btnEl.href, "_blank");
            btnEl.textContent = origText;
          });
        }
      }

      primaryBtn.addEventListener("click", (e) => triggerDirectInstallerDownload(e, isLinux ? "linux" : "windows", primaryBtn));
      winBtn.addEventListener("click", (e) => triggerDirectInstallerDownload(e, "windows", winBtn));
      linuxBtn.addEventListener("click", (e) => triggerDirectInstallerDownload(e, "linux", linuxBtn));

      card.appendChild(header);
      card.appendChild(desc);
      card.appendChild(actions);
      modal.appendChild(card);

      document.body.appendChild(modal);

      closeBtn.addEventListener("click", () => {
        modal.classList.remove("turbodm-modal-visible");
      });
      modal.addEventListener("click", (e) => {
        if (e.target === modal) modal.classList.remove("turbodm-modal-visible");
      });
    }
    modal.classList.add("turbodm-modal-visible");
  }

  /**
   * Dispatches download to background script.
   */
  function triggerDownload(targetEl, audioOnly = false) {
    const url = resolveTargetUrl(targetEl);
    if (!url) return;

    const btn = getOrCreateOverlayButton();
    setButtonContent(btn, "⏳", "Sending to Turbo DM...", false);

    if (!api || !api.runtime) {
      showAppRequiredModal();
      resetOverlayButtonState(btn);
      return;
    }

    try {
      api.runtime.sendMessage({
        action: "DOWNLOAD_MEDIA",
        url: url,
        audioOnly: audioOnly,
        referrer: window.location.href
      }).then((resp) => {
        if (resp && resp.success) {
          btn.classList.add("turbodm-success");
          setButtonContent(btn, "⚡", audioOnly ? "Audio Sent to Turbo DM!" : "Queued in Turbo DM!", false);
          setTimeout(() => {
            resetOverlayButtonState(btn);
            scheduleHide(600);
          }, 2200);
        } else if (resp && resp.fallback) {
          // Sent via protocol fallback
          setButtonContent(btn, "⚡", "Launching Turbo DM...", false);
          setTimeout(() => {
            resetOverlayButtonState(btn);
          }, 2000);
        } else {
          showAppRequiredModal();
          resetOverlayButtonState(btn);
        }
      }).catch((err) => {
        showAppRequiredModal();
        resetOverlayButtonState(btn);
      });
    } catch (err) {
      showAppRequiredModal();
      resetOverlayButtonState(btn);
    }
  }

  /**
   * Locates video element or video container under point or element.
   */
  function findVideoOrContainer(el) {
    if (!el || el === document.body || el === document.documentElement) return null;

    // Direct video element
    if (el.tagName === "VIDEO") return el;

    // Embedded video iframe
    if (el.tagName === "IFRAME") {
      const src = el.src || "";
      if (src.includes("youtube.com") || src.includes("vimeo.com") || src.includes("player.")) {
        return el;
      }
    }

    // Common player containers across popular platforms
    const playerSelectors = [
      "#movie_player",
      ".html5-video-player",
      "ytd-player",
      "ytd-watch-flexy #player",
      "ytd-rich-grid-media:has(video)",
      "ytd-reel-video-renderer",
      "div[data-testid='videoComponent']",
      "div[data-testid='videoPlayer']",
      "div[data-pagelet*='Video']",
      "div[data-a-target='video-player']",
      "div[data-a-target='player-overlay-click-handler']",
      ".video-player__container",
      ".highwind-video-player",
      "article:has(video)",
      "div[class*='video-player']",
      "div[class*='player-container']",
      ".video-container"
    ];

    for (const sel of playerSelectors) {
      try {
        const found = el.closest(sel);
        if (found) return found;
      } catch (e) {}
    }

    // Fallback: Check if element contains or is sibling to a video
    const container = el.closest("div, section, article");
    if (container) {
      const vid = container.querySelector("video");
      if (vid) return container;
    }

    return null;
  }

  /**
   * Positions and reveals the overlay button.
   */
  function showOverlayFor(target) {
    if (!isOverlayEnabled || !target) return;

    const rect = target.getBoundingClientRect();
    if (rect.width < 120 || rect.height < 70) return; // Ignore tiny elements/icons

    const btn = getOrCreateOverlayButton();
    mountButton(btn);
    activeTarget = target;

    const isFullscreen = !!(document.fullscreenElement || document.webkitFullscreenElement);
    const scrollX = isFullscreen ? 0 : (window.scrollX || window.pageXOffset || 0);
    const scrollY = isFullscreen ? 0 : (window.scrollY || window.pageYOffset || 0);

    // Position in the top-right corner of the video frame
    const top = rect.top + scrollY + 14;
    const left = rect.right + scrollX - 235;

    btn.style.top = `${Math.max(10, top)}px`;
    btn.style.left = `${Math.max(10, left)}px`;

    if (hideTimer) {
      clearTimeout(hideTimer);
      hideTimer = null;
    }

    btn.classList.add("turbodm-visible");
  }

  function scheduleHide(delay = 600) {
    if (hideTimer) clearTimeout(hideTimer);
    hideTimer = setTimeout(() => {
      if (overlayBtn) {
        overlayBtn.classList.remove("turbodm-visible");
      }
    }, delay);
  }

  /**
   * Throttled global mousemove listener.
   * Completely avoids duplicate event listeners and MutationObserver thrashing.
   */
  document.addEventListener("mousemove", (e) => {
    const now = Date.now();
    if (now - lastMoveTime < 40) return; // Throttle to ~25fps for maximum performance
    lastMoveTime = now;

    // If mouse is hovering over the button itself, do not hide
    if (overlayBtn && overlayBtn.contains(e.target)) {
      if (hideTimer) {
        clearTimeout(hideTimer);
        hideTimer = null;
      }
      return;
    }

    const videoOrContainer = findVideoOrContainer(e.target);
    if (videoOrContainer) {
      showOverlayFor(videoOrContainer);
    } else if (overlayBtn && overlayBtn.classList.contains("turbodm-visible")) {
      scheduleHide(600);
    }
  }, { passive: true });

  // Hide overlay on scroll
  window.addEventListener("scroll", () => {
    if (overlayBtn && overlayBtn.classList.contains("turbodm-visible")) {
      scheduleHide(200);
    }
  }, { passive: true });

  // Handle SPA navigation (YouTube, Facebook, Twitter, Instagram)
  window.addEventListener("yt-navigate-finish", () => {
    scheduleHide(0);
    setTimeout(tryInjectYouTubePlaylistButton, 400);
    setTimeout(tryInjectYouTubePlaylistButton, 1200);
  });
  window.addEventListener("popstate", () => {
    scheduleHide(0);
    setTimeout(tryInjectYouTubePlaylistButton, 500);
  });

  // =========================================================
  // YouTube Playlist Integration & Modal Downloader
  // =========================================================

  function sanitizeFilename(str) {
    if (!str) return "Track";
    return str.replace(/[<>:"/\\|?*\x00-\x1F]/g, "_").trim();
  }

  function getCleanVideoUrl(rawUrl) {
    if (!rawUrl) return "";
    try {
      const u = new URL(rawUrl, window.location.origin);
      const v = u.searchParams.get("v");
      if (v) return `https://www.youtube.com/watch?v=${v}`;
      if (u.pathname.includes("/watch")) return u.origin + u.pathname + (v ? `?v=${v}` : "");
      return rawUrl;
    } catch (e) {
      return rawUrl;
    }
  }

  /**
   * Scans DOM for YouTube Playlist tracks and metadata with robust multi-selector fallbacks.
   */
  function extractPlaylistData() {
    try {
      const urlObj = new URL(window.location.href);
      let playlistTitle = "";
      let channelName = "YouTube";
      let tracks = [];

      // 1. Try finding playlist title across all possible YouTube containers
      const titleSelectors = [
        "ytd-playlist-panel-renderer .title",
        "ytd-playlist-panel-renderer #header-description h3",
        "ytd-playlist-panel-renderer yt-formatted-string.title",
        "ytd-playlist-panel-renderer #title",
        "ytd-playlist-header-renderer yt-formatted-string#text",
        "ytd-playlist-header-renderer .title",
        "ytd-browse[page-subtype='playlist'] #title",
        "h1#title",
        "ytd-page-header-renderer h1"
      ];
      for (const sel of titleSelectors) {
        const el = document.querySelector(sel);
        if (el && el.textContent && el.textContent.trim()) {
          playlistTitle = el.textContent.trim();
          break;
        }
      }

      if (!playlistTitle) {
        playlistTitle = document.title ? document.title.replace(/\s*-\s*YouTube$/i, "").trim() : "YouTube Playlist";
      }

      // 2. Try finding channel / author name
      const channelSelectors = [
        "ytd-playlist-panel-renderer #publisher-container",
        "ytd-playlist-panel-renderer byline-container",
        "ytd-playlist-panel-renderer #byline",
        "ytd-playlist-header-renderer yt-formatted-string#owner-text",
        "ytd-playlist-header-renderer .byline",
        "#channel-name",
        "#owner #channel-name"
      ];
      for (const sel of channelSelectors) {
        const el = document.querySelector(sel);
        if (el && el.textContent && el.textContent.trim()) {
          channelName = el.textContent.trim().replace(/\s*-\s*\d+\s*\/\s*\d+.*$/, "").trim();
          break;
        }
      }

      // 3. Scan for track items
      const seenUrls = new Set();

      const itemNodes = document.querySelectorAll(
        "ytd-playlist-panel-video-renderer, " +
        "#playlist-items ytd-playlist-panel-video-renderer, " +
        "ytd-playlist-video-renderer, " +
        "ytd-item-section-renderer ytd-playlist-video-renderer, " +
        "ytd-playlist-video-list-renderer ytd-playlist-video-renderer"
      );

      itemNodes.forEach((node, idx) => {
        try {
          const titleNode = node.querySelector("#video-title, span#video-title, yt-formatted-string#video-title, h4");
          const title = titleNode ? (titleNode.textContent || titleNode.title || "").trim() : `Track ${idx + 1}`;
          const linkNode = node.querySelector("a#wc-endpoint, a#thumbnail, a#video-title, a[href*='/watch']");
          const rawHref = linkNode ? linkNode.href : "";
          const cleanUrl = getCleanVideoUrl(rawHref);
          const timeNode = node.querySelector("#time-status, .ytd-thumbnail-overlay-time-status-renderer, span.ytd-thumbnail-overlay-time-status-renderer, #length");
          const duration = timeNode ? timeNode.textContent.trim() : "";

          if (cleanUrl && !seenUrls.has(cleanUrl)) {
            seenUrls.add(cleanUrl);
            tracks.push({
              index: tracks.length + 1,
              title: title || `Track ${tracks.length + 1}`,
              url: cleanUrl,
              duration: duration
            });
          }
        } catch (e) {}
      });

      // If no track nodes found via renderers, scan all links in playlist container
      if (tracks.length === 0) {
        const playlistContainer = document.querySelector("ytd-playlist-panel-renderer, ytd-playlist-video-list-renderer, #playlist, ytd-browse[page-subtype='playlist']");
        if (playlistContainer) {
          const linkElements = playlistContainer.querySelectorAll("a[href*='/watch']");
          linkElements.forEach((a) => {
            const cleanUrl = getCleanVideoUrl(a.href);
            if (cleanUrl && !seenUrls.has(cleanUrl)) {
              seenUrls.add(cleanUrl);
              const titleText = a.textContent ? a.textContent.trim() : "";
              tracks.push({
                index: tracks.length + 1,
                title: (titleText.length > 3 && !titleText.includes(":")) ? titleText : `Track ${tracks.length + 1}`,
                url: cleanUrl,
                duration: ""
              });
            }
          });
        }
      }

      // If still 0, fallback to current video / playlist URL
      if (tracks.length === 0) {
        const currentUrl = window.location.href;
        const currentClean = getCleanVideoUrl(currentUrl);
        tracks.push({
          index: 1,
          title: playlistTitle || "Current Video / Playlist",
          url: currentClean || currentUrl,
          duration: ""
        });
      }

      if (playlistTitle && playlistTitle.includes("•")) {
        playlistTitle = playlistTitle.split("•")[0].trim();
      }

      return {
        title: playlistTitle || "YouTube Playlist",
        channel: channelName || "YouTube",
        tracks: tracks
      };
    } catch (err) {
      console.error("[TurboDM] Error extracting playlist data:", err);
      return {
        title: document.title ? document.title.replace(/\s*-\s*YouTube$/i, "").trim() : "YouTube Playlist",
        channel: "YouTube",
        tracks: [{
          index: 1,
          title: document.title || "Playlist Track",
          url: window.location.href,
          duration: ""
        }]
      };
    }
  }

  /**
   * Spawns the interactive Turbo DM Playlist Downloader Modal.
   */
  function openPlaylistModal(plData) {
    let modal = document.getElementById("turbodm-playlist-modal");
    if (modal) {
      modal.remove();
    }

    modal = document.createElement("div");
    modal.id = "turbodm-playlist-modal";
    modal.className = "turbodm-modal-overlay";

    const card = document.createElement("div");
    card.className = "turbodm-playlist-modal-card";

    // Header
    const header = document.createElement("div");
    header.className = "turbodm-playlist-header";

    const titleWrap = document.createElement("div");
    titleWrap.className = "turbodm-playlist-title-wrap";

    const title = document.createElement("div");
    title.className = "turbodm-playlist-title";
    title.textContent = "⚡ Turbo Playlist Downloader";

    const badge = document.createElement("span");
    badge.className = "turbodm-playlist-badge";
    badge.textContent = `${plData.tracks.length || 0} TRACKS`;

    titleWrap.appendChild(title);
    titleWrap.appendChild(badge);

    const closeBtn = document.createElement("button");
    closeBtn.className = "turbodm-modal-close";
    closeBtn.textContent = "✕";

    header.appendChild(titleWrap);
    header.appendChild(closeBtn);

    // Body
    const body = document.createElement("div");
    body.className = "turbodm-playlist-body";

    // Playlist Meta Banner
    const metaBanner = document.createElement("div");
    metaBanner.className = "turbodm-pl-meta-banner";

    const metaInfo = document.createElement("div");
    metaInfo.className = "turbodm-pl-meta-info";

    const nameDisp = document.createElement("div");
    nameDisp.className = "turbodm-pl-name-display";
    nameDisp.textContent = plData.title;

    const chanDisp = document.createElement("div");
    chanDisp.className = "turbodm-pl-channel-display";
    chanDisp.textContent = `${plData.channel} • ${plData.tracks.length} videos detected`;

    metaInfo.appendChild(nameDisp);
    metaInfo.appendChild(chanDisp);
    metaBanner.appendChild(metaInfo);
    body.appendChild(metaBanner);

    // Destination Folder Input
    const folderGroup = document.createElement("div");
    folderGroup.className = "turbodm-form-group";

    const folderLabel = document.createElement("label");
    folderLabel.className = "turbodm-form-label";
    folderLabel.innerHTML = "📁 <span>Save Subfolder / Folder Name:</span>";

    const folderInput = document.createElement("input");
    folderInput.type = "text";
    folderInput.className = "turbodm-input-box";
    folderInput.value = sanitizeFilename(plData.title);
    folderInput.placeholder = "Enter folder name for this playlist...";

    const folderHelp = document.createElement("div");
    folderHelp.className = "turbodm-form-help";
    folderHelp.textContent = "Creates this subfolder inside your default Turbo DM downloads directory to organize all tracks.";

    folderGroup.appendChild(folderLabel);
    folderGroup.appendChild(folderInput);
    folderGroup.appendChild(folderHelp);
    body.appendChild(folderGroup);

    // Download Format (Audio vs Video)
    const formatGroup = document.createElement("div");
    formatGroup.className = "turbodm-form-group";

    const formatLabel = document.createElement("label");
    formatLabel.className = "turbodm-form-label";
    formatLabel.innerHTML = "🎛️ <span>Download Format:</span>";

    const formatGrid = document.createElement("div");
    formatGrid.className = "turbodm-segment-grid";

    let selectedFormat = "audio"; // Default audio for music playlists
    const audioBtn = document.createElement("button");
    audioBtn.type = "button";
    audioBtn.className = "turbodm-segment-btn active";
    audioBtn.innerHTML = "🎵 <span>Audio Only (MP3 320k)</span>";

    const videoBtn = document.createElement("button");
    videoBtn.type = "button";
    videoBtn.className = "turbodm-segment-btn";
    videoBtn.innerHTML = "📹 <span>Full Video (MP4)</span>";

    audioBtn.addEventListener("click", () => {
      selectedFormat = "audio";
      audioBtn.classList.add("active");
      videoBtn.classList.remove("active");
    });

    videoBtn.addEventListener("click", () => {
      selectedFormat = "video";
      videoBtn.classList.add("active");
      audioBtn.classList.remove("active");
    });

    formatGrid.appendChild(audioBtn);
    formatGrid.appendChild(videoBtn);
    formatGroup.appendChild(formatLabel);
    formatGroup.appendChild(formatGrid);
    body.appendChild(formatGroup);

    // File Naming Pattern
    const namingGroup = document.createElement("div");
    namingGroup.className = "turbodm-form-group";

    const namingLabel = document.createElement("label");
    namingLabel.className = "turbodm-form-label";
    namingLabel.innerHTML = "🏷️ <span>File Naming Pattern:</span>";

    const namingSelect = document.createElement("select");
    namingSelect.className = "turbodm-input-box";
    namingSelect.style.cursor = "pointer";

    const optNumbered = document.createElement("option");
    optNumbered.value = "numbered";
    optNumbered.textContent = "01 - Track Title (Sequential Numbering - Recommended)";
    optNumbered.selected = true;

    const optStandard = document.createElement("option");
    optStandard.value = "standard";
    optStandard.textContent = "Track Title Only";

    const optArtistTitle = document.createElement("option");
    optArtistTitle.value = "artist_title";
    optArtistTitle.textContent = `${plData.channel || "Artist"} - Track Title`;

    namingSelect.appendChild(optNumbered);
    namingSelect.appendChild(optStandard);
    namingSelect.appendChild(optArtistTitle);

    namingGroup.appendChild(namingLabel);
    namingGroup.appendChild(namingSelect);
    body.appendChild(namingGroup);

    // Track Selection Checklist
    const tracklistContainer = document.createElement("div");
    tracklistContainer.className = "turbodm-tracklist-container";

    const tracklistHeader = document.createElement("div");
    tracklistHeader.className = "turbodm-tracklist-header";

    const countLabel = document.createElement("span");
    countLabel.id = "turbodmTrackCountLabel";
    countLabel.textContent = `Tracks: ${plData.tracks.length} / ${plData.tracks.length} Selected`;

    const toggleAllBtn = document.createElement("button");
    toggleAllBtn.type = "button";
    toggleAllBtn.className = "turbodm-toggle-all-btn";
    toggleAllBtn.textContent = "Deselect All";

    tracklistHeader.appendChild(countLabel);
    tracklistHeader.appendChild(toggleAllBtn);
    tracklistContainer.appendChild(tracklistHeader);

    const trackScroll = document.createElement("div");
    trackScroll.className = "turbodm-tracklist-scroll";

    const checkboxes = [];

    plData.tracks.forEach((track, idx) => {
      const row = document.createElement("label");
      row.className = "turbodm-track-row";

      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = true;
      cb.style.accentColor = "#00d2ff";
      cb.style.cursor = "pointer";
      cb.dataset.index = idx;
      checkboxes.push(cb);

      cb.addEventListener("change", () => {
        updateSelectedCount();
      });

      const num = document.createElement("span");
      num.className = "turbodm-track-num";
      num.textContent = String(idx + 1).padStart(2, "0");

      const trackTitle = document.createElement("span");
      trackTitle.className = "turbodm-track-title";
      trackTitle.textContent = track.title;

      const dur = document.createElement("span");
      dur.className = "turbodm-track-duration";
      dur.textContent = track.duration || "";

      row.appendChild(cb);
      row.appendChild(num);
      row.appendChild(trackTitle);
      row.appendChild(dur);
      trackScroll.appendChild(row);
    });

    tracklistContainer.appendChild(trackScroll);
    body.appendChild(tracklistContainer);

    function updateSelectedCount() {
      const selected = checkboxes.filter((c) => c.checked).length;
      countLabel.textContent = `Tracks: ${selected} / ${checkboxes.length} Selected`;
      toggleAllBtn.textContent = selected === checkboxes.length ? "Deselect All" : "Select All";
      submitBtn.textContent = `🚀 Download Entire Playlist (${selected} Items)`;
      submitBtn.disabled = selected === 0;
      submitBtn.style.opacity = selected === 0 ? "0.5" : "1";
    }

    let allSelected = true;
    toggleAllBtn.addEventListener("click", () => {
      allSelected = !allSelected;
      checkboxes.forEach((c) => { c.checked = allSelected; });
      updateSelectedCount();
    });

    // Footer
    const footer = document.createElement("div");
    footer.className = "turbodm-playlist-footer";

    const cancelBtn = document.createElement("button");
    cancelBtn.type = "button";
    cancelBtn.className = "turbodm-btn-cancel";
    cancelBtn.textContent = "Cancel";

    const submitBtn = document.createElement("button");
    submitBtn.type = "button";
    submitBtn.className = "turbodm-btn-submit";
    submitBtn.textContent = `🚀 Download Entire Playlist (${plData.tracks.length} Items)`;

    footer.appendChild(cancelBtn);
    footer.appendChild(submitBtn);

    card.appendChild(header);
    card.appendChild(body);
    card.appendChild(footer);
    const mountTarget = document.fullscreenElement || document.webkitFullscreenElement || document.body || document.documentElement;
    mountTarget.appendChild(modal);

    // Event handlers
    closeBtn.addEventListener("click", () => modal.classList.remove("turbodm-modal-visible"));
    cancelBtn.addEventListener("click", () => modal.classList.remove("turbodm-modal-visible"));
    modal.addEventListener("click", (e) => {
      if (e.target === modal) modal.classList.remove("turbodm-modal-visible");
    });

    // Submit handler
    submitBtn.addEventListener("click", () => {
      const selectedIndices = checkboxes
        .map((cb, i) => (cb.checked ? i : -1))
        .filter((i) => i >= 0);

      if (selectedIndices.length === 0) return;

      const subfolderName = sanitizeFilename(folderInput.value.trim() || plData.title);
      const isAudioOnly = selectedFormat === "audio";
      const ext = isAudioOnly ? ".mp3" : ".mp4";
      const namingMode = namingSelect.value;

      const itemsPayload = selectedIndices.map((idx, orderIdx) => {
        const track = plData.tracks[idx];
        let fname = sanitizeFilename(track.title);

        if (namingMode === "numbered") {
          const pad = String(orderIdx + 1).padStart(2, "0");
          fname = `${pad} - ${fname}${ext}`;
        } else if (namingMode === "artist_title" && plData.channel) {
          fname = `${sanitizeFilename(plData.channel)} - ${fname}${ext}`;
        } else {
          fname = `${fname}${ext}`;
        }

        return {
          url: track.url,
          filename: fname,
          audio_only: isAudioOnly
        };
      });

      submitBtn.textContent = "⏳ Sending to Turbo DM...";
      submitBtn.disabled = true;

      if (!api || !api.runtime) {
        showAppRequiredModal();
        modal.classList.remove("turbodm-modal-visible");
        return;
      }

      api.runtime.sendMessage({
        action: "DOWNLOAD_PLAYLIST",
        items: itemsPayload,
        subfolder: subfolderName,
        playlistTitle: plData.title,
        audioOnly: isAudioOnly
      }).then((resp) => {
        if (resp && resp.success) {
          body.innerHTML = `
            <div class="turbodm-pl-success-state">
              <div class="turbodm-pl-success-icon">⚡</div>
              <div class="turbodm-pl-success-title">Playlist Queued Successfully!</div>
              <div class="turbodm-pl-success-desc">
                <strong>${itemsPayload.length} tracks</strong> sent to Turbo Download Manager.<br>
                Saving to subfolder: <code style="color: #00d2ff; background: rgba(0,210,255,0.1); padding: 2px 6px; border-radius: 4px;">Downloads/${subfolderName}/</code>
              </div>
            </div>
          `;
          footer.style.display = "none";
          setTimeout(() => {
            modal.classList.remove("turbodm-modal-visible");
          }, 2200);
        } else {
          showAppRequiredModal();
          modal.classList.remove("turbodm-modal-visible");
        }
      }).catch((err) => {
        showAppRequiredModal();
        modal.classList.remove("turbodm-modal-visible");
      });
    });

    // Animate and display modal immediately
    modal.classList.add("turbodm-modal-visible");
    modal.style.zIndex = "2147483647";
    modal.style.display = "flex";
  }

  /**
   * Injects the Turbo DM download button directly into YouTube's Playlist action bars.
   */
  function tryInjectYouTubePlaylistButton() {
    const isYouTube = window.location.hostname.includes("youtube.com");
    if (!isYouTube) return;

    // 1. Check Watch Page playlist panel action buttons (as in the user's screenshot)
    const watchPanel = document.querySelector("ytd-playlist-panel-renderer, #playlist");
    if (watchPanel) {
      const actionsContainer = watchPanel.querySelector("#top-level-buttons, .top-level-buttons, #playlist-actions, #header-contents, .header-description, #header-top");
      if (actionsContainer && !actionsContainer.querySelector(".turbodm-yt-playlist-btn")) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "turbodm-yt-playlist-btn";
        btn.title = "Download Entire Playlist with Turbo DM";
        btn.innerHTML = `<span class="turbodm-pl-icon" style="pointer-events:none;">⚡</span><span class="turbodm-pl-label" style="pointer-events:none;">Download Playlist</span>`;

        actionsContainer.insertBefore(btn, actionsContainer.firstChild);
      }
    }

    // 2. Check Playlist Overview Page (/playlist?list=...)
    const playlistHeader = document.querySelector("ytd-playlist-header-renderer, ytd-browse[page-subtype='playlist']");
    if (playlistHeader) {
      const actionsBar = playlistHeader.querySelector("#top-level-buttons-computed, .action-buttons, #top-level-buttons, #buttons");
      if (actionsBar && !actionsBar.querySelector(".turbodm-yt-playlist-btn")) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "turbodm-yt-playlist-btn";
        btn.title = "Download Entire Playlist with Turbo DM";
        btn.innerHTML = `<span class="turbodm-pl-icon" style="pointer-events:none;">⚡</span><span class="turbodm-pl-label" style="pointer-events:none;">Download Entire Playlist (Turbo DM)</span>`;

        actionsBar.insertBefore(btn, actionsBar.firstChild);
      }
    }
  }

  // Global Capture Phase Click Listener - bypasses YouTube Polymer event cancellation
  document.addEventListener("click", (e) => {
    const btn = e.target && e.target.closest ? e.target.closest(".turbodm-yt-playlist-btn") : null;
    if (btn) {
      e.stopPropagation();
      e.preventDefault();
      try {
        const plData = extractPlaylistData();
        openPlaylistModal(plData);
      } catch (err) {
        console.error("[TurboDM] Failed to open playlist modal:", err);
      }
    }
  }, true);

  // Periodic check when on YouTube to catch dynamically loaded playlist elements
  if (window.location.hostname.includes("youtube.com")) {
    setInterval(tryInjectYouTubePlaylistButton, 1200);
    setTimeout(tryInjectYouTubePlaylistButton, 300);
    setTimeout(tryInjectYouTubePlaylistButton, 1000);
    setTimeout(tryInjectYouTubePlaylistButton, 2500);
  }

})();

