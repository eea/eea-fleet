#!/bin/bash

# Rancher CLI Installation/Upgrade Script
# Supports macOS, Linux, and Windows (via WSL)

set -e

RANCHER_CLI_VERSION="v2.8.0"  # You can update this to the latest version
INSTALL_DIR="/usr/local/bin"
TEMP_DIR="/tmp/rancher-cli-install"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Detect OS and architecture
detect_platform() {
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m)
    
    case $OS in
        darwin)
            OS="darwin"
            ;;
        linux)
            OS="linux"
            ;;
        msys*|mingw*|cygwin*)
            OS="windows"
            ;;
        *)
            print_error "Unsupported operating system: $OS"
            exit 1
            ;;
    esac
    
    case $ARCH in
        x86_64|amd64)
            ARCH="amd64"
            ;;
        arm64|aarch64)
            ARCH="arm64"
            ;;
        i386|i686)
            ARCH="386"
            ;;
        *)
            print_error "Unsupported architecture: $ARCH"
            exit 1
            ;;
    esac
    
    print_status "Detected platform: $OS-$ARCH"
}

# Check if rancher CLI is already installed
check_existing_installation() {
    if command -v rancher >/dev/null 2>&1; then
        CURRENT_VERSION=$(rancher --version 2>/dev/null | grep -o 'v[0-9]\+\.[0-9]\+\.[0-9]\+' | head -1 || echo "unknown")
        print_status "Rancher CLI is already installed: $CURRENT_VERSION"
        
        if [ "$CURRENT_VERSION" = "$RANCHER_CLI_VERSION" ]; then
            print_success "Already running the target version ($RANCHER_CLI_VERSION)"
            exit 0
        else
            print_warning "Current version ($CURRENT_VERSION) differs from target ($RANCHER_CLI_VERSION)"
            read -p "Do you want to upgrade/downgrade? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                print_status "Installation cancelled"
                exit 0
            fi
        fi
    else
        print_status "Rancher CLI not found, proceeding with installation"
    fi
}

# Try Homebrew installation on macOS
try_homebrew_install() {
    if [[ "$OS" == "darwin" ]] && command -v brew >/dev/null 2>&1; then
        print_status "Trying Homebrew installation..."
        
        if brew list rancher-cli >/dev/null 2>&1; then
            print_status "Upgrading via Homebrew..."
            brew upgrade rancher-cli || brew install rancher-cli
        else
            print_status "Installing via Homebrew..."
            brew install rancher-cli
        fi
        
        if command -v rancher >/dev/null 2>&1; then
            NEW_VERSION=$(rancher --version 2>/dev/null | grep -o 'v[0-9]\+\.[0-9]\+\.[0-9]\+' | head -1 || echo "installed")
            print_success "Rancher CLI installed via Homebrew: $NEW_VERSION"
            return 0
        fi
    fi
    return 1
}

# Download and install from GitHub releases
download_and_install() {
    print_status "Downloading Rancher CLI $RANCHER_CLI_VERSION for $OS-$ARCH..."
    
    # Create temp directory
    mkdir -p "$TEMP_DIR"
    cd "$TEMP_DIR"
    
    # Construct download URL
    if [[ "$OS" == "windows" ]]; then
        FILENAME="rancher-$OS-$ARCH-$RANCHER_CLI_VERSION.zip"
        EXTRACT_CMD="unzip -q"
        BINARY_NAME="rancher.exe"
    else
        FILENAME="rancher-$OS-$ARCH-$RANCHER_CLI_VERSION.tar.gz"
        EXTRACT_CMD="tar -xzf"
        BINARY_NAME="rancher"
    fi
    
    DOWNLOAD_URL="https://github.com/rancher/cli/releases/download/$RANCHER_CLI_VERSION/$FILENAME"
    
    # Download
    if command -v curl >/dev/null 2>&1; then
        curl -L -o "$FILENAME" "$DOWNLOAD_URL"
    elif command -v wget >/dev/null 2>&1; then
        wget -O "$FILENAME" "$DOWNLOAD_URL"
    else
        print_error "Neither curl nor wget found. Please install one of them."
        exit 1
    fi
    
    # Extract
    print_status "Extracting..."
    $EXTRACT_CMD "$FILENAME"
    
    # Find the binary
    BINARY_PATH=$(find . -name "$BINARY_NAME" -type f | head -1)
    if [[ -z "$BINARY_PATH" ]]; then
        print_error "Could not find rancher binary in extracted files"
        exit 1
    fi
    
    # Make executable
    chmod +x "$BINARY_PATH"
    
    # Install
    print_status "Installing to $INSTALL_DIR..."
    
    # Check if we need sudo
    if [[ ! -w "$INSTALL_DIR" ]]; then
        print_warning "Need sudo privileges to install to $INSTALL_DIR"
        sudo cp "$BINARY_PATH" "$INSTALL_DIR/rancher"
        sudo chmod +x "$INSTALL_DIR/rancher"
    else
        cp "$BINARY_PATH" "$INSTALL_DIR/rancher"
    fi
    
    # Cleanup
    cd - >/dev/null
    rm -rf "$TEMP_DIR"
    
    print_success "Rancher CLI installed successfully!"
}

# Verify installation
verify_installation() {
    if command -v rancher >/dev/null 2>&1; then
        INSTALLED_VERSION=$(rancher --version 2>/dev/null | grep -o 'v[0-9]\+\.[0-9]\+\.[0-9]\+' | head -1 || echo "unknown")
        print_success "Installation verified: $INSTALLED_VERSION"
        
        print_status "Rancher CLI is ready to use!"
        print_status "Next steps:"
        echo "  1. Login to your Rancher server: rancher login https://your-rancher-server"
        echo "  2. Select a context: rancher context switch"
        echo "  3. List projects: rancher projects ls"
        
        return 0
    else
        print_error "Installation verification failed"
        return 1
    fi
}

# Main installation flow
main() {
    echo "==================================="
    echo "  Rancher CLI Installation Script  "
    echo "==================================="
    echo
    
    detect_platform
    check_existing_installation
    
    # Try Homebrew first on macOS
    if [[ "$OS" == "darwin" ]] && try_homebrew_install; then
        verify_installation
        exit 0
    fi
    
    # Fallback to direct download
    download_and_install
    verify_installation
}

# Run main function
main "$@"