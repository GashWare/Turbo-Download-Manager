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
  });
  window.addEventListener("popstate", () => {
    scheduleHide(0);
  });

})();
