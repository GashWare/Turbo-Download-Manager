#!/usr/bin/env bash
# ==============================================================================
# Turbo Download Manager - Universal Linux Installer & Bootloader
# Supports: Ubuntu, Debian, Mint, Pop!_OS, Fedora, RHEL, CentOS, Arch, Manjaro,
#           Alpine, openSUSE, and other modern Linux distributions.
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv"

# Color Codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}======================================================${NC}"
echo -e "${CYAN}       TURBO DOWNLOAD MANAGER - LINUX INSTALLER       ${NC}"
echo -e "${CYAN}======================================================${NC}"

# Detect Linux Distribution
DISTRO="unknown"
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO=$ID
    DISTRO_LIKE=${ID_LIKE:-$ID}
fi

echo -e "${BLUE}[*] Detected Distribution:${NC} $DISTRO ($DISTRO_LIKE)"

# Function to check command availability
has_cmd() {
    command -v "$1" >/dev/null 2>&1
}

# Function to install system packages based on distro
install_system_dependencies() {
    echo -e "${YELLOW}[+] Verifying system prerequisites (Python 3, Tkinter, Pip, Venv)...${NC}"
    
    case "$DISTRO" in
        ubuntu|debian|linuxmint|pop|elementary|zorin|kali)
            echo -e "${BLUE}[*] Using apt package manager...${NC}"
            sudo apt-get update -y
            sudo apt-get install -y python3 python3-pip python3-tk python3-venv xdg-utils
            ;;
        fedora|rhel|centos|rocky|alma)
            echo -e "${BLUE}[*] Using dnf package manager...${NC}"
            sudo dnf install -y python3 python3-pip python3-tkinter xdg-utils
            ;;
        arch|manjaro|endeavouros|garuda)
            echo -e "${BLUE}[*] Using pacman package manager...${NC}"
            sudo pacman -Sy --noconfirm python python-pip tk xdg-utils
            ;;
        opensuse*|suse)
            echo -e "${BLUE}[*] Using zypper package manager...${NC}"
            sudo zypper refresh
            sudo zypper install -y python3 python3-pip python3-tk xdg-utils
            ;;
        alpine)
            echo -e "${BLUE}[*] Using apk package manager...${NC}"
            sudo apk update
            sudo apk add python3 py3-pip py3-tkinter xdg-utils
            ;;
        *)
            if [[ "$DISTRO_LIKE" == *"debian"* ]] || [[ "$DISTRO_LIKE" == *"ubuntu"* ]]; then
                sudo apt-get update -y && sudo apt-get install -y python3 python3-pip python3-tk python3-venv xdg-utils
            elif [[ "$DISTRO_LIKE" == *"rhel"* ]] || [[ "$DISTRO_LIKE" == *"fedora"* ]]; then
                sudo dnf install -y python3 python3-pip python3-tkinter xdg-utils
            elif [[ "$DISTRO_LIKE" == *"arch"* ]]; then
                sudo pacman -Sy --noconfirm python python-pip tk xdg-utils
            else
                echo -e "${RED}[!] Unrecognized distro '$DISTRO'. Please ensure python3, python3-tk, and python3-venv are installed manually.${NC}"
            fi
            ;;
    esac
}

# Check if Python 3 is installed and if tkinter is available
NEEDS_SYS_INSTALL=0
if ! has_cmd python3; then
    NEEDS_SYS_INSTALL=1
elif ! python3 -c "import tkinter" >/dev/null 2>&1; then
    echo -e "${YELLOW}[!] Python is present, but tkinter is missing.${NC}"
    NEEDS_SYS_INSTALL=1
fi

if [ $NEEDS_SYS_INSTALL -eq 1 ]; then
    install_system_dependencies
fi

# Create Isolated Virtual Environment (PEP 668 Compliant)
echo -e "${BLUE}[*] Setting up Python Virtual Environment in $VENV_DIR...${NC}"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

# Activate Virtual Environment
source "$VENV_DIR/bin/activate"

# Upgrade pip & install requirements
echo -e "${BLUE}[*] Upgrading pip and installing dependencies into venv...${NC}"
pip install --upgrade pip setuptools wheel
pip install -r "$ROOT_DIR/Python/requirements.txt"

# Set executable permissions for launcher scripts
chmod +x "$SCRIPT_DIR/run_gui.sh" "$SCRIPT_DIR/run_cli.sh"

# Create Desktop Application Shortcut (.desktop)
DESKTOP_DIR="$HOME/.local/share/applications"
if [ -d "$HOME/.local/share" ]; then
    mkdir -p "$DESKTOP_DIR"
    DESKTOP_FILE="$DESKTOP_DIR/turbo-downloader.desktop"
    
    cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Turbo Download Manager
Comment=Accelerated Multi-Connection Download Engine
Exec=$SCRIPT_DIR/run_gui.sh
Icon=$ROOT_DIR/Python/gui/assets/app_icon.png
Terminal=false
Categories=Network;FileTransfer;
StartupNotify=true
EOF
    chmod +x "$DESKTOP_FILE"
    echo -e "${GREEN}[✓] Desktop launcher installed: $DESKTOP_FILE${NC}"
fi

echo -e ""
echo -e "${GREEN}======================================================${NC}"
echo -e "${GREEN}   TURBO DOWNLOAD MANAGER INSTALLED SUCCESSFULLY!     ${NC}"
echo -e "${GREEN}======================================================${NC}"
echo -e "You can launch the application anytime using:"
echo -e "  - GUI Mode: ${CYAN}$SCRIPT_DIR/run_gui.sh${NC} (or from your App Launcher)"
echo -e "  - CLI Mode: ${CYAN}$SCRIPT_DIR/run_cli.sh add <URL>${NC}"
echo -e ""