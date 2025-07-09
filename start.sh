#!/bin/bash

# 🚀 SPREADSHEET Q&A ASSISTANT - ONE CLICK START
# This script handles EVERYTHING - just run it!

set -e

# Colors for beautiful output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

# Banner
clear
echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════╗"
echo "║                                                       ║"
echo "║        📊 SPREADSHEET Q&A ASSISTANT                   ║"
echo "║           One-Click Installation & Start              ║"
echo "║                                                       ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo

# Check if we're in the right directory
if [ ! -f "src/app.py" ]; then
    print_error "Please run this script from the project root directory"
    exit 1
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check Python
print_status "Checking Python installation..."
if command_exists python3; then
    PYTHON_CMD="python3"
elif command_exists python; then
    PYTHON_CMD="python"
else
    print_error "Python is not installed!"
    print_info "Please install Python 3.9+ from https://python.org"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
print_success "Python $PYTHON_VERSION found"

# Check/Create virtual environment
if [ ! -d "venv" ]; then
    print_status "Creating virtual environment..."
    $PYTHON_CMD -m venv venv
    print_success "Virtual environment created"
else
    print_success "Virtual environment exists"
fi

# Activate virtual environment
print_status "Activating virtual environment..."
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi

# Check Ollama FIRST (before slow Python installs)
print_status "Checking for Ollama (required for AI features)..."
if ! command_exists ollama; then
    print_error "Ollama is not installed!"
    echo
    print_info "Ollama is required for AI features. Please install it first:"
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        print_info "For macOS, Ollama needs to be downloaded manually"
        print_info "Download from: https://ollama.com/download/mac"
        echo
        read -p "Press Enter after installing Ollama to continue..."
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        print_info "Installing Ollama automatically..."
        curl -fsSL https://ollama.com/install.sh | sh
        echo
        print_info "Ollama installation attempted. Checking..."
    else
        print_info "Download from: https://ollama.com/download"
        echo
        read -p "Press Enter after installing Ollama to continue..."
    fi
    
    if ! command_exists ollama; then
        print_error "Ollama still not found. Please install it and run this script again."
        exit 1
    fi
fi
print_success "Ollama found"

# Install/Update pip
print_status "Updating pip..."
pip install --upgrade pip --quiet

# Count packages to install
TOTAL_PACKAGES=$(grep -c "^[^#]" src/requirements.txt | tr -d ' ')
print_status "Installing $TOTAL_PACKAGES Python packages..."
print_info "This typically takes 5-15 minutes on first install"
echo

# Function to show simplified progress
show_progress() {
    local current=0
    while IFS= read -r line; do
        if [[ "$line" == *"Collecting"* ]]; then
            ((current++))
            printf "\r📦 Installing packages: [%-50s] %d/%d" "$(printf '#%.0s' $(seq 1 $((current*50/TOTAL_PACKAGES))))" "$current" "$TOTAL_PACKAGES"
        elif [[ "$line" == *"ERROR"* ]] || [[ "$line" == *"error"* ]]; then
            echo -e "\n$line"
        fi
    done
    echo -e "\n"
}

# Install requirements with simplified output
pip install -r src/requirements.txt --no-cache-dir 2>&1 | show_progress || {
    print_error "Package installation failed! Trying minimal requirements..."
    echo
    pip install -r src/requirements-minimal.txt --no-cache-dir -q || {
        print_error "Minimal installation also failed!"
        print_info "Common fixes:"
        print_info "1. Delete venv/ folder and try again"
        print_info "2. Check your internet connection"
        exit 1
    }
    print_info "Installed minimal requirements successfully"
}

print_success "All packages installed"

# Ollama already checked above, just verify it's running

# Start Ollama if not running
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    print_status "Starting Ollama..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        open -a Ollama
    else
        ollama serve >/dev/null 2>&1 &
    fi
    
    # Wait for Ollama to start
    print_status "Waiting for Ollama to start..."
    for i in {1..30}; do
        if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
            break
        fi
        sleep 1
    done
fi
print_success "Ollama is running"

# Check for required models
print_status "Checking AI models..."
MODELS_NEEDED=false

if ! ollama list | grep -q "llama3.2"; then
    print_info "Language model not found. Downloading (~2GB, takes 3-10 minutes)..."
    echo "Progress:"
    ollama pull llama3.2
    MODELS_NEEDED=true
fi

if ! ollama list | grep -q "mxbai-embed-large"; then
    print_info "Embedding model not found. Downloading (~400MB, takes 1-3 minutes)..."
    echo "Progress:"
    ollama pull mxbai-embed-large
    MODELS_NEEDED=true
fi

if [ "$MODELS_NEEDED" = true ]; then
    print_success "AI models downloaded successfully"
else
    print_success "AI models already installed"
fi

# Final preparation
echo
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✨ Everything is ready! Starting the app...${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo

# Launch the app
print_info "Opening http://localhost:8501 in your browser..."
echo
print_info "To stop the app, press Ctrl+C"
echo

# Start Streamlit
streamlit run src/app.py --theme.base="dark" --theme.primaryColor="#3182ce"