#!/bin/bash
# EEA Fleet TUI Installation Script
# This script installs the EEA Fleet TUI executable to a system location

set -e

# Configuration
APP_NAME="eea-fleet-tui"
INSTALL_DIR="/usr/local/bin"
EXECUTABLE="dist/${APP_NAME}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_permissions() {
    if [[ $EUID -eq 0 ]]; then
        log_warning "Running as root. Installation will proceed to ${INSTALL_DIR}"
        return 0
    else
        log_info "Not running as root. Will attempt to use sudo for installation"
        if ! command -v sudo &> /dev/null; then
            log_error "sudo is required for installation to ${INSTALL_DIR}"
            exit 1
        fi
        return 1
    fi
}

# Check if executable exists
check_executable() {
    if [[ ! -f "${EXECUTABLE}" ]]; then
        log_error "Executable not found: ${EXECUTABLE}"
        log_info "Please run the build process first:"
        log_info "  pyinstaller eea-fleet-tui.spec"
        exit 1
    fi
    
    if [[ ! -x "${EXECUTABLE}" ]]; then
        log_error "File is not executable: ${EXECUTABLE}"
        exit 1
    fi
    
    log_success "Found executable: ${EXECUTABLE}"
}

# Install the executable
install_executable() {
    local use_sudo=$1
    local cmd_prefix=""
    
    if [[ $use_sudo -eq 1 ]]; then
        cmd_prefix="sudo "
    fi
    
    log_info "Installing ${APP_NAME} to ${INSTALL_DIR}..."
    
    # Create install directory if it doesn't exist
    ${cmd_prefix}mkdir -p "${INSTALL_DIR}"
    
    # Copy executable
    ${cmd_prefix}cp "${EXECUTABLE}" "${INSTALL_DIR}/${APP_NAME}"
    
    # Set permissions
    ${cmd_prefix}chmod +x "${INSTALL_DIR}/${APP_NAME}"
    
    log_success "Installed ${APP_NAME} to ${INSTALL_DIR}/${APP_NAME}"
}

# Verify installation
verify_installation() {
    if command -v "${APP_NAME}" &> /dev/null; then
        log_success "Installation verified. ${APP_NAME} is available in PATH"
        log_info "You can now run: ${APP_NAME}"
    else
        log_warning "Installation completed but ${APP_NAME} is not in PATH"
        log_info "You may need to add ${INSTALL_DIR} to your PATH"
        log_info "Or run directly: ${INSTALL_DIR}/${APP_NAME}"
    fi
}

# Create desktop entry (Linux only)
create_desktop_entry() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        local desktop_dir="$HOME/.local/share/applications"
        local desktop_file="${desktop_dir}/eea-fleet-tui.desktop"
        
        if [[ ! -d "$desktop_dir" ]]; then
            mkdir -p "$desktop_dir"
        fi
        
        cat > "$desktop_file" << EOF
[Desktop Entry]
Name=EEA Fleet TUI
Comment=Modern terminal interface for generating Rancher Fleet configurations for EEA Helm charts
Exec=${INSTALL_DIR}/${APP_NAME}
Icon=utilities-terminal
Terminal=true
Type=Application
Categories=Development;System;
Keywords=kubernetes;helm;fleet;eea;
EOF
        
        chmod +x "$desktop_file"
        log_success "Created desktop entry: $desktop_file"
    fi
}

# Main installation process
main() {
    log_info "EEA Fleet TUI Installation Script"
    log_info "================================="
    
    # Check if executable exists
    check_executable
    
    # Check permissions
    if check_permissions; then
        use_sudo=0
    else
        use_sudo=1
    fi
    
    # Install executable
    install_executable $use_sudo
    
    # Verify installation
    verify_installation
    
    # Create desktop entry (Linux only)
    create_desktop_entry
    
    echo
    log_success "Installation completed successfully!"
    log_info "Run '${APP_NAME}' to start the EEA Fleet Configuration Generator"
}

# Show help
show_help() {
    cat << EOF
EEA Fleet TUI Installation Script

Usage: $0 [OPTIONS]

Options:
    -h, --help          Show this help message
    -d, --install-dir   Specify installation directory (default: ${INSTALL_DIR})

Examples:
    $0                  Install to default location (${INSTALL_DIR})
    $0 -d ~/.local/bin  Install to user's local bin directory

Requirements:
    - Executable must be built first (run: pyinstaller eea-fleet-tui.spec)
    - sudo access for system-wide installation
    - Or write permissions to target directory

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -d|--install-dir)
            INSTALL_DIR="$2"
            shift 2
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Run main installation
main