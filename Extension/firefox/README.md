# Turbo Download Manager - Firefox Browser Extension

Official Firefox browser extension for **Turbo Download Manager**. Seamlessly bridges your Firefox browsing experience with the high-performance Turbo Download Manager desktop engine.

---

## ⚡ Features

- **🚀 Auto-Interception**: Automatically intercepts browser downloads (ZIP, EXE, ISO, MP4, etc.) and routes them through Turbo DM for multi-connection parallel acceleration.
- **🎥 Video Hover Overlay**: Hover over any video player across any website (YouTube, X / Twitter, Instagram Reels, Facebook Videos, TikTok, Vimeo, Twitch clips) to reveal the floating **⚡ Download with Download Manager** button.
- **🎵 Audio-Only Extraction**: Instant one-click extraction to MP3 directly from video hover controls or popup.
- **🖱️ Context Menu Integration**: Right-click any link, video, audio, or page to immediately download with Turbo DM.
- **🔌 Zero Configuration REST IPC**: Communicates directly with Turbo Download Manager on `http://127.0.0.1:9666` with automatic fallback to `turbodm://` protocol.

---

## 📦 How to Install in Firefox

### Method 1: Load Temporary Add-on (Development / Testing)
1. Open Firefox and type `about:debugging#/runtime/this-firefox` in the address bar.
2. Click **Load Temporary Add-on...**
3. Navigate to `Extension/firefox/manifest.json` and select it.
4. The extension is now active in Firefox!

### Method 2: Packaged ZIP / XPI
1. You can zip the contents of `Extension/firefox/` into `turbodm-firefox.xpi` or `turbodm-firefox.zip`.
2. Load in `about:addons` or install permanently via signed add-on.

---

## ⚙️ Configuration & Options

Click the Turbo DM icon in the Firefox toolbar to open the popup:
- **Intercept Browser Downloads**: Toggle automatic redirection of file downloads.
- **Video Hover Button**: Toggle overlay on streaming platforms and HTML5 video tags.
- **Auto-Start Tasks**: Choose between adding tasks directly into the active download queue or opening the confirmation dialog.
- **Quick Download / Video Capture**: Paste any media or file link to accelerate immediately.
