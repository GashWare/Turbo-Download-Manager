# ⚡ Turbo Download Manager

An enterprise-grade, high-performance, and feature-rich download accelerator for Python, equipped with a modern **CustomTkinter GUI** (with 6 cyber themes & matrix rain) and a live **Interactive Terminal CLI** (powered by Rich).

---

## 🌟 Key Features

### 🚀 Acceleration & Engine Innovations
- **Parallel Multi-Connection Range Requests**: Splits downloads into 1–32 concurrent worker threads using HTTP Range requests (`RFC 7233`) to maximize bandwidth saturation.
- **Adaptive Dynamic Work-Stealing**: Idle worker threads continuously identify lagging segments, dynamically splitting remaining byte ranges in real time to eliminate tail latency.
- **Zero-Delay Direct I/O**: Target files are pre-allocated, and worker threads write directly into byte offsets using thread-safe random access—eliminating post-download file concatenation delay.
- **Adaptive Buffer Scaling**: Dynamically scales chunk read buffers from 64 KB up to 512 KB according to real-time throughput.
- **Crash Recovery & True Resumability**: Checkpoints segment byte offsets to `.dm_meta.json`. Interrupted or paused downloads resume only remaining chunks with exponential backoff auto-reconnect.
- **Duplicate & Collision Protection**: Automatically resolves duplicate filenames (e.g. `file (1).ext`) preventing data clobbering.

### 🧲 BitTorrent & Magnet Link Engine (`libtorrent 2.1.1`)
- **Universal Torrent & Magnet Support**: Direct downloading of `magnet:?xt=...` URI links and `.torrent` files.
- **"Leech Only" Mode (Enabled by default)**: Zero-upload mode that caps upload bandwidth, disables unchoke slots, and auto-pauses immediately upon download completion to prevent seeding.
- **Sequential Downloading**: Enforces in-order piece retrieval for media streaming and sequential playback.
- **P2P Fine-Tuning**: Configurable Max Peer connections, Download Speed Limits, Upload Speed Limits, and DHT (Distributed Hash Table) peer discovery.

### 🌐 Browser & System Protocol Associations
- **1-Click Browser Integration**: Registers `magnet:`, `turbodm:` URI schemes and `.torrent` file associations across Windows (`HKCU\Software\Classes\` without requiring administrator privileges) and Linux (`xdg-mime` / FreeDesktop `.desktop`).
- **Supported Browsers**: Automatically intercepts clicks from Google Chrome, Microsoft Edge, Mozilla Firefox, Brave, Opera, and Windows Explorer.
- **Live Status Badges**: View and toggle protocol handler registration directly in the Settings menu or via CLI flags (`--register-protocols`, `--unregister-protocols`).

### 🦊 Official Firefox Browser Extension
- **Auto-Interception**: Intercepts native browser file downloads (ZIP, EXE, ISO, MP4, etc.) and routes them to Turbo DM for multi-connection acceleration.
- **Floating Video Hover Overlay**: Hovering over any video player across any site (YouTube, X/Twitter, Instagram Reels, Facebook Videos, TikTok, Vimeo, Twitch clips) displays a sleek **⚡ Download with Download Manager** button.
- **1-Click MP3 Extraction**: Extract audio directly from the hover overlay or popup window.
- **Embedded Zero-Config API**: Communicates via local background HTTP server (`http://127.0.0.1:9666`) with instant `turbodm://` protocol fallback.
- **Ready-to-Install Packages**: Included in `Extension/firefox/` and packaged as `.zip` / `.xpi` in `Distributions/`.

### 🎬 Social Video & Streaming Media Extractor (`yt-dlp`)
- **Universal Multi-Platform Support**: High-definition video and audio stream extractor for X (Twitter), Instagram Reels & Posts, Facebook Reels & Videos, YouTube, TikTok, Vimeo, Reddit, and 1,000+ streaming sites.
- **Facebook Videos & Reels**: Native accelerated downloading for Facebook Reels (`facebook.com/reel/...`), Facebook Watch, Facebook Stories, and share links.
- **X / Twitter & Instagram**: Instant capture of video posts, timelines, and Reels.
- **Audio Only Extraction**: Dynamic toggle to extract pristine audio into MP3 (320kbps), M4A, AAC, WAV, FLAC, or OPUS.
- **Quality & Container Presets**: Select video resolution (4K 2160p, 1440p, 1080p Full HD, 720p HD, 480p, etc.) and output format (MP4, MKV, WebM).
- **Isolated Temp Storage & Auto-Cleanup**: Intermediate stream fragments and audio/video muxing files are isolated in a dedicated system temp folder and completely wiped upon final compilation.
- **Concurrent Fragment Acceleration**: Multi-threaded parallel stream chunk downloading (8–32 connections).

### 🛡️ Bandwidth & Security Control
- **Token-Bucket Bandwidth Regulator**: Smooth global or per-download speed caps (500 KB/s, 1 MB/s, 5 MB/s, 10 MB/s, 20 MB/s, Unlimited).
- **Cryptographic Hash Verifier**: SHA-256, SHA-512, SHA-1, and MD5 file integrity calculator and automatic verification.
- **Smart Clipboard Monitor**: Background listener that detects copied download URLs and prompts immediate downloads.

---

## 🎨 User Interfaces

### 1. Modern CustomTkinter GUI
- **6 Rich Dynamic Themes**:
  - 🌙 **Dark**: Sleek Cyber Slate (Default)
  - ☀️ **Light**: Modern Clean Slate Light
  - 🌆 **Cyberpunk**: Night City Neon Yellow, Cyan & Pink
  - 🔮 **Neon**: Synthwave Electric Purple & Cyan
  - 🗼 **Neo Tokyo**: Midnight Aqua & Crimson
  - 🟩 **Matrix**: Terminal Phosphor Green, Obsidian & Animated Digital Rain Canvas
  - *Theme persistence*: Selected theme is saved automatically and restored seamlessly on startup.
- **Visual Segment Canvas**: Visualizes real-time segment chunk blocks filling up with multi-threaded connection status (flicker-free cached rendering).
- **One-Click File & Folder Actions**:
  - **Open**: Directly launches completed downloads with the system default application.
  - **Open Folder**: Opens the native File Explorer / Manager (`explorer.exe`, `nautilus`, `dolphin`, `xdg-open`, `Finder`) and automatically selects/highlights the file.
- **Dynamic ETA Formatting**: Formats remaining download time adaptively (`< 60s` -> `45s`, `> 60s` -> `2m 5s`, `> 60m` -> `1h 12m 30s`).
- **Category Filter Sidebar**: Categorizes files into All, Video, Audio, Documents, Compressed, Programs, Images, and Torrents.
- **New Download Modal**: Real-time URL prober with auto-detected file size, range support status, thread slider, torrent options card, media options card, and checksum input.
- **Batch Add URLs Modal**: Paste multiple links and queue them in bulk.
- **Right-Click Context Menu**:
  - Start / Resume / Pause
  - Re-download from scratch
  - Copy Download URL / File Path
  - Open File / Open Folder & Reveal
  - Task Inspector & Hash Integrity Check
  - Delete Download
- **Cross-Platform Audio & Desktop Alerts**: Plays native completion chimes and shows desktop notifications across Windows, Linux (`notify-send`, `paplay`, `canberra`), and macOS.

### 2. Rich Animated CLI
- **Live Terminal Visualizer**: Interactive segmented block bar, real-time speed, transferred size, seed/peer count, and adaptive ETA metrics.
- **Interactive Live Dashboard (`monitor`)**: Full-screen live updating TUI table rendering active throughput, progress, and download statuses.
- **Batch Downloads (`batch`)**: Download multiple URLs from a text file or comma-separated list.
- **P2P & Torrent Flags**: Direct CLI torrent downloads with `--leech-only`, `--sequential`, and `--max-peers`.

---

## 📁 Project Structure

```
Turbo Download Manager/
├── README.md                      # Comprehensive project documentation
├── MSI/
│   └── Turbo Download Manager-2.0.0-win64.msi # Standalone Windows MSI Installer
├── Distributions/
│   ├── Turbo-Download-Manager-2.0.0-Windows-Portable.zip # Windows Portable Release
│   ├── Turbo-Download-Manager-2.0.0-Linux.tar.gz         # Linux Standalone Tarball
│   └── Turbo-Download-Manager-2.0.0-Linux.zip            # Linux Portable Release
├── Batch/
│   ├── install_windows.bat        # Windows automated bootloader & installer
│   ├── build_msi.bat              # 1-Click MSI compilation script
│   ├── run_gui.bat                # Windows Batch GUI launcher
│   └── run_cli.bat                # Windows Batch CLI launcher
├── PowerShell/
│   ├── install_windows.ps1        # PowerShell automated installer & shortcut creator
│   ├── build_msi.ps1              # PowerShell MSI compilation script
│   ├── copy_distributions.ps1     # Distribution package packaging & synchronization script
│   ├── run_gui.ps1                # PowerShell GUI launcher
│   └── run_cli.ps1                # PowerShell CLI launcher
├── Shell/
│   ├── install_linux.sh           # Linux universal distro installer (venv + pkgs + .desktop)
│   ├── run_gui.sh                 # Linux Shell GUI launcher
│   └── run_cli.sh                 # Linux Shell CLI launcher
└── Python/
    ├── requirements.txt           # Python package dependencies
    ├── setup_msi.py               # cx_Freeze MSI packaging configuration
    ├── main.py                    # Master entry point & protocol router
    ├── core/
    │   ├── __init__.py
    │   ├── models.py              # Data models, Enums, metadata persistence
    │   ├── os_utils.py            # Cross-platform OS detection, file reveal, alerts
    │   ├── categories.py          # Extension & MIME classifier (Videos, Torrents, etc.)
    │   ├── checksum.py            # Cryptographic hash verification (SHA256, MD5, etc.)
    │   ├── rate_limiter.py        # Token-bucket bandwidth regulator
    │   ├── prober.py              # URL capability prober, magnet & torrent metadata inspector
    │   ├── segment_downloader.py  # Multi-threaded work-stealing HTTP engine
    │   ├── stream_downloader.py   # Non-range streaming fallback engine
    │   ├── media_downloader.py    # High-speed stream media extractor (yt-dlp)
    │   ├── torrent_downloader.py  # BitTorrent & Magnet engine (libtorrent 2.1.1)
    │   ├── protocol_handler.py    # Cross-platform browser magnet & .torrent registration
    │   ├── clipboard_monitor.py   # Background clipboard URL listener
    │   └── queue_manager.py       # Central scheduler, thread pool & session database
    ├── cli/
    │   ├── __init__.py
    │   └── cli_app.py             # Rich terminal application
    ├── gui/
    │   ├── __init__.py
    │   ├── gui_app.py             # Main CustomTkinter application window
    │   ├── themes.py              # 6 Dynamic Theme Palettes (Dark, Light, Cyberpunk, Neon, Neo Tokyo, Matrix)
    │   ├── assets/                # App icons (.ico & .png)
    │   └── components/
    │       ├── __init__.py
    │       ├── download_card.py   # Download card with segment block canvas & folder actions
    │       ├── add_dialog.py      # Add Download modal (HTTP, Streams, BitTorrent)
    │       ├── batch_add_dialog.py# Batch Add URLs modal
    │       ├── details_dialog.py  # Task inspector & hash validator modal
    │       ├── matrix_rain.py     # High-performance Matrix phosphor digital rain canvas & hover animators
    │       └── settings_dialog.py # Preferences, themes, bandwidth limits & protocol association modal
    └── tests/
        ├── __init__.py
        ├── test_downloader.py     # HTTP range, pause/resume, themes, and GUI unit test suite
        └── test_torrent.py        # BitTorrent, Leech Only mode, and protocol handler test suite
```

---

## 🚀 Installation & Bootloaders

### 🪟 Windows Setup

#### Option A: Native MSI Installer (Recommended)
Double-click the pre-built installer:
- **`MSI\Turbo Download Manager-2.0.0-win64.msi`**
- Installs standalone `TurboDownloadManager.exe` and `turbo-cli.exe` with Desktop & Start Menu shortcuts, and registers system `PATH`.
- Rebuild MSI anytime via `Batch\build_msi.bat` or `PowerShell\build_msi.ps1`.

#### Option B: Automated Script Bootloader
Run either script to automatically check for Python, set up an isolated `.venv`, and install dependencies:
- **Command Prompt**: Double-click `Batch\install_windows.bat`
- **PowerShell**: `.\PowerShell\install_windows.ps1`

### 🐧 Linux Setup (Ubuntu, Debian, Mint, Fedora, Arch, Alpine, openSUSE)
The universal Linux installer auto-detects your system package manager (`apt`, `dnf`, `pacman`, `zypper`, `apk`), verifies `python3`, `python3-tk`, and creates a PEP-668 compliant isolated virtual environment (`.venv`):
```bash
chmod +x Shell/install_linux.sh
./Shell/install_linux.sh
```

---

## 💻 Launching & CLI Usage

### GUI Mode
- **Windows**: Double-click `Batch\run_gui.bat` or `PowerShell\run_gui.ps1`
- **Linux**: `./Shell/run_gui.sh` or launch **Turbo Download Manager** from your desktop app menu.
- **Python direct**: `python Python/main.py --gui`

### CLI Commands & Examples

- **Accelerated HTTP Download (16 Parallel Threads)**:
  ```bash
  python Python/main.py download "https://example.com/largefile.zip" -n 16
  ```

- **BitTorrent / Magnet Download in Leech Only Mode**:
  ```bash
  python Python/main.py download "magnet:?xt=urn:btih:..." --leech-only --sequential
  ```

- **Batch Download URLs from File**:
  ```bash
  python Python/main.py batch "urls.txt" -n 8 -o "C:\Downloads"
  ```

- **Open Live Full-Screen Terminal Dashboard (TUI)**:
  ```bash
  python Python/main.py monitor
  ```

- **Task Queue Operations**:
  ```bash
  python Python/main.py list
  python Python/main.py pause <task_id>
  python Python/main.py resume <task_id>
  python Python/main.py cancel <task_id>
  python Python/main.py status <task_id>
  ```

- **Browser Protocol Registration via CLI**:
  ```bash
  python Python/main.py --register-protocols
  python Python/main.py --unregister-protocols
  ```

---

## 🧪 Running Automated Tests

Run the complete test suite across all download engines, themes, torrent subsystems, and protocol handlers:
```bash
python -m unittest discover -s Python/tests -v
```

---

## 📄 License
This project is open source and available under the MIT License.
