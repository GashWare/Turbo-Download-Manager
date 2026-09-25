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
   * Lazily creates the single shared overlay button DOM node.
   */
  function getOrCreateOverlayButton() {
    if (overlayBtn && overlayBtn.parentNode) {
      return overlayBtn;
    }

    overlayBtn = document.createElement("div");
    overlayBtn.id = "turbodm-floating-overlay";
    overlayBtn.className = "turbodm-video-overlay-btn";
    overlayBtn.innerHTML = `
      <span class="turbodm-icon" style="pointer-events:none;">⚡</span>
      <span class="turbodm-text" style="pointer-events:none;">Download with Turbo DM</span>
      <span class="turbodm-audio-opt" title="Download Audio Only (MP3)">MP3</span>
    `;

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

    // 5. TikTok / Reddit / Vimeo / Dailymotion
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

      modal.innerHTML = `
        <div class="turbodm-modal-card">
          <div class="turbodm-modal-header">
            <div class="turbodm-modal-title">⚡ Turbo Download Manager Desktop Required</div>
            <button class="turbodm-modal-close" id="turbodmModalClose">✕</button>
          </div>
          <p class="turbodm-modal-desc">
            To download and capture video streams at maximum accelerated speeds, the Turbo Download Manager desktop software is required.
          </p>
          <div class="turbodm-modal-actions">
            <a href="${primaryUrl}" target="_blank" class="turbodm-modal-btn primary">
              ${primaryLabel}
            </a>
            <div class="turbodm-modal-grid">
              <a href="https://github.com/GashWare/Turbo-Download-Manager/raw/main/MSI/Turbo%20Download%20Manager-2.0.0-win64.msi" target="_blank" class="turbodm-modal-btn secondary">
                🪟 Windows Installer
              </a>
              <a href="https://github.com/GashWare/Turbo-Download-Manager/raw/main/Distributions/Turbo-Download-Manager-2.0.0-Linux.tar.gz" target="_blank" class="turbodm-modal-btn secondary">
                🐧 Linux Package
              </a>
            </div>
            <a href="https://github.com/GashWare/Turbo-Download-Manager" target="_blank" class="turbodm-modal-link">
              📦 View on GitHub Releases & Documentation
            </a>
          </div>
        </div>
      `;
      document.body.appendChild(modal);

      modal.querySelector("#turbodmModalClose").addEventListener("click", () => {
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
    const originalContent = btn.innerHTML;

    btn.innerHTML = `
      <span class="turbodm-icon" style="pointer-events:none;">⏳</span>
      <span class="turbodm-text" style="pointer-events:none;">Sending to Turbo DM...</span>
    `;

    if (!api || !api.runtime) {
      showAppRequiredModal();
      btn.innerHTML = originalContent;
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
          btn.innerHTML = `
            <span class="turbodm-icon" style="pointer-events:none;">⚡</span>
            <span class="turbodm-text" style="pointer-events:none;">${audioOnly ? "Audio Sent to Turbo DM!" : "Queued in Turbo DM!"}</span>
          `;
          setTimeout(() => {
            btn.classList.remove("turbodm-success");
            btn.innerHTML = originalContent;
            scheduleHide(600);
          }, 2200);
        } else if (resp && resp.fallback) {
          // Sent via protocol fallback
          btn.innerHTML = `
            <span class="turbodm-icon" style="pointer-events:none;">⚡</span>
            <span class="turbodm-text" style="pointer-events:none;">Launching Turbo DM...</span>
          `;
          setTimeout(() => {
            btn.innerHTML = originalContent;
          }, 2000);
        } else {
          showAppRequiredModal();
          btn.innerHTML = originalContent;
        }
      }).catch((err) => {
        showAppRequiredModal();
        btn.innerHTML = originalContent;
      });
    } catch (err) {
      showAppRequiredModal();
      btn.innerHTML = originalContent;
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
