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

# Install requirements with clean output
echo "📦 Installing packages (this will take 5-15 minutes)..."
echo "   Please be patient - no news is good news!"
echo
pip install -r src/requirements.txt --no-cache-dir -q --disable-pip-version-check || {
    print_error "Package installation failed! Trying minimal requirements..."
    echo
    pip install -r src/requirements-minimal.txt --no-cache-dir -q --disable-pip-version-check || {
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

# Detect hardware and recommend models
print_status "Detecting hardware capabilities..."
AVAILABLE_RAM=$(python3 -c "import psutil; print(int(psutil.virtual_memory().available / (1024**3)))" 2>/dev/null || echo "8")

# Check if Apple Silicon
IS_APPLE_SILICON=false
APPLE_CHIP=""
if [[ "$OSTYPE" == "darwin"* ]]; then
    CHIP_STRING=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo "")
    if echo "$CHIP_STRING" | grep -q "Apple"; then
        IS_APPLE_SILICON=true
        # Extract chip model
        for chip in "M3 Max" "M3 Pro" "M3" "M2 Ultra" "M2 Max" "M2 Pro" "M2" "M1 Ultra" "M1 Max" "M1 Pro" "M1"; do
            if echo "$CHIP_STRING" | grep -q "$chip"; then
                APPLE_CHIP="$chip"
                break
            fi
        done
        print_info "🍎 Apple Silicon detected: ${APPLE_CHIP:-Apple Silicon}"
        print_info "✨ Ollama automatically uses Metal GPU acceleration for optimal performance"
        
        # Check if MLX is available for even better performance
        if python3 -c "import mlx" 2>/dev/null; then
            print_success "MLX is installed - additional optimization available"
        else
            print_info "💡 For even better performance, consider installing MLX:"
            print_info "   pip install mlx-lm"
        fi
    fi
fi

# Select appropriate models based on RAM
if [ "$AVAILABLE_RAM" -lt 4 ]; then
    EMBEDDING_MODEL="all-minilm"
    LLM_MODEL="phi3:mini"
    print_info "Limited RAM detected. Using lightweight models."
elif [ "$AVAILABLE_RAM" -lt 8 ]; then
    EMBEDDING_MODEL="nomic-embed-text"
    LLM_MODEL="llama3.2:3b-instruct-q4_K_M"
    print_info "Moderate RAM detected. Using balanced models."
else
    EMBEDDING_MODEL="mxbai-embed-large"
    LLM_MODEL="mistral:7b-instruct-q4_K_M"
    print_info "Sufficient RAM detected. Using high-quality models."
fi

# Check and download embedding model
if ! ollama list | grep -q "$EMBEDDING_MODEL"; then
    print_info "Embedding model ($EMBEDDING_MODEL) not found. Downloading..."
    echo "Progress:"
    ollama pull $EMBEDDING_MODEL
    MODELS_NEEDED=true
fi

# Check and download language model
if ! ollama list | grep -q "$LLM_MODEL"; then
    print_info "Language model ($LLM_MODEL) not found. Downloading..."
    echo "Progress:"
    ollama pull $LLM_MODEL
    MODELS_NEEDED=true
fi

# Also ensure we have the basic models for compatibility
if ! ollama list | grep -q "llama3.2"; then
    print_info "Downloading default language model for compatibility..."
    ollama pull llama3.2:latest
fi

if ! ollama list | grep -q "mxbai-embed-large"; then
    print_info "Downloading default embedding model for compatibility..."
    ollama pull mxbai-embed-large
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