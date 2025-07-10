# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Spreadsheet Q&A Assistant with a professional Streamlit web interface that enables natural language queries over CSV files and Google Sheets using local LLMs. Features one-click installation and a dark-themed UI designed for executive demos.

## Key Commands

### Running the Application

```bash
# ONE COMMAND TO RULE THEM ALL
./start.sh                                      # macOS/Linux - handles everything
start.bat                                       # Windows - handles everything

# Manual alternatives (if needed)
streamlit run src/app.py                        # Direct Streamlit launch
python src/api_server.py                        # REST API server

# The start script automatically:
# - Checks/installs Python packages
# - Checks/guides Ollama installation  
# - Downloads AI models if needed
# - Launches the web app
```

### Common Development Tasks

```bash
# Install dependencies
pip install -r src/requirements.txt

# Pull required Ollama models (one-time setup)
ollama pull llama3.2
ollama pull mxbai-embed-large

# Clear vector store when switching data sources
rm -rf ./chroma_db_clients/

# Check Python syntax
python -m py_compile src/*.py

# Run with sample data
streamlit run src/app.py  # Sample data is built-in
```

## Architecture & Key Design Decisions

### Core Components

1. **Web UI**: `app.py` - Streamlit interface (primary user interface)
2. **Data Loading**: `vector.py:load_client_data()` - Handles CSV and Google Sheets
3. **Document Creation**: `vector.py:create_documents()` - Converts DataFrame rows to searchable documents
4. **Vector Storage**: `vector.py:get_retriever()` - Factory for ChromaDB (local) or Pinecone (cloud)
5. **API Server**: `api_server.py` - REST API for programmatic access
6. **Model Selection**: `model_selector_v2.py` - Hardware detection and intelligent model recommendations
7. **Model Backends**: `model_backends.py` - Abstraction for Ollama and MLX (Apple Silicon optimization)

### Module Relationships

```
app.py (Streamlit Web UI - PRIMARY INTERFACE)
    ├── vector.py (core data handling)
    │   ├── gsheet_loader.py (Google Sheets support)
    │   └── pinecone_vector.py (cloud vector storage)
    └── Uses LangChain for query processing

api_server.py (REST API - SECONDARY)
    └── Uses same vector.py core
```

### Key Design Patterns

1. **Web-First Design**: Streamlit UI is the primary interface, not CLI
2. **Factory Pattern**: `get_retriever()` switches between vector stores
3. **Flexible Schema**: Dynamically adapts to any CSV structure
4. **Sample Data**: Built-in sample data for demos (`sample_data.csv`)

### Important Implementation Details

- **UI Framework**: Streamlit 1.40+ for web interface
- **Vector Store**: ChromaDB (local) by default, Pinecone for cloud
- **Google Sheets**: Must be publicly viewable
- **Embeddings**: Dynamic selection based on hardware (mxbai-embed-large, nomic-embed-text, all-minilm)
- **LLM**: Dynamic selection based on hardware (mistral, qwen2.5, llama3.2, phi3)
- **Port**: 8501 for Streamlit, 8000 for API server
- **Hardware Detection**: Automatic model selection based on available RAM/GPU
- **Apple Silicon**: Automatic Metal GPU acceleration via Ollama
- **MLX Support**: Optional MLX framework for additional Apple Silicon optimization

### Environment Variables

```bash
CLIENT_DATA_SOURCE      # Default data source (optional - UI handles this)
VECTOR_STORE_TYPE       # "chroma" (default) or "pinecone"
PINECONE_API_KEY        # Required if using Pinecone
PINECONE_INDEX_NAME     # Pinecone index (default: "client-tracker")
OLLAMA_HOST             # Ollama server (default: http://localhost:11434)
```

## UI Features

The Streamlit app (`src/app.py`) includes:
- Sidebar for data source selection (CSV upload, Google Sheets URL)
- Model Settings panel with hardware detection and model selection
- Chat interface with message history
- Quick questions in main chat area for easy access
- Data preview functionality
- Source document display
- Professional dark theme with better colors

## Model Recommendations by Hardware

### Minimal Setup (< 4GB RAM)
- **Embedding**: all-minilm (45MB)
- **LLM**: phi3:mini (2.2GB)

### Balanced Setup (4-8GB RAM)  
- **Embedding**: nomic-embed-text (274MB)
- **LLM**: llama3.2:3b-instruct-q4_K_M (2GB)

### Premium Setup (8GB+ RAM)
- **Embedding**: mxbai-embed-large (560MB)
- **LLM**: mistral:7b-instruct-q4_K_M (4.1GB) or qwen2.5:7b-instruct-q4_K_M (4.4GB)

### Apple Silicon Optimized
- Automatic detection of specific chip (M1/M2/M3 variants)
- Ollama uses Metal GPU acceleration automatically
- Unified memory architecture for efficient model loading
- Optional MLX support for future enhancements
- Chip-specific optimizations:
  - M1: 8 GPU cores, 16 Neural Engine cores
  - M1 Pro/Max: 16-32 GPU cores, higher memory bandwidth
  - M2: 10 GPU cores, improved efficiency
  - M3: Enhanced GPU architecture, Dynamic Caching

## Common Issues & Solutions

1. **"Ollama not found"**: Ensure Ollama is running (`ollama serve`)
2. **Google Sheets access denied**: Sheet must be "Anyone with link can view"
3. **Out of memory**: Use Model Settings to select smaller models
4. **Streamlit not loading**: Check port 8501 isn't in use
5. **Import errors**: Run from project root directory
6. **Model download fails**: Check internet connection and disk space
7. **Embedding dimension mismatch**: Fixed automatically! The app now handles this
8. **Quick questions not working**: Fixed! They now trigger immediately
9. **"psutil not installed"**: Run `pip install psutil` or use `./start.sh`
10. **ChromaDB readonly error**: Fixed automatically! Permissions are corrected on the fly
11. **M4 chip not detected**: Fixed! Now properly detects M4, M4 Pro, M4 Max

## Project Structure Notes

- `src/app.py` - Main Streamlit web application
- `src/api_server.py` - REST API (secondary interface)
- `src/vector.py` - Core data handling logic
- `start.sh` - One-click installer/launcher for macOS/Linux
- `start.bat` - One-click installer/launcher for Windows
- `./chroma_db_clients/` - Vector storage (gitignored)
- `src/model_backends.py` - MLX and Ollama backend abstraction
- `src/model_selector_v2.py` - Hardware detection and model recommendations
- NO `chat_interface.py` - CLI has been removed

## Recent Major Changes (v2.4.0)

### UI/UX Improvements
- **Automatic Data Loading** - Files and Google Sheets load automatically when selected (no button needed)
- **Seamless Model Switching** - Data automatically reloads when embedding model changes
- **Improved Model Selection** - Clear indicators for installed (✅) vs downloadable (⬇️) models
- **Smart Button States** - Buttons show "No Changes" when nothing to apply
- **URL Validation** - Google Sheets URLs are validated before loading

### Performance & Infrastructure
- **MLX Support Added** - Optional MLX-LM installation for Apple Silicon optimization
- **M4 Chip Detection** - Full support for latest M4, M4 Pro, M4 Max chips
- **Better Error Handling** - ChromaDB permission errors are automatically fixed
- **Model Backend Architecture** - Ready for MLX integration alongside Ollama

### Apple Silicon Enhancements
- **Chip-Specific Detection** - Identifies exact M1/M2/M3/M4 variants
- **Metal Acceleration** - Automatic GPU usage via Ollama
- **MLX Backend Ready** - Infrastructure for MLX models with performance benefits
- **Unified Memory Aware** - Optimizes for Apple's memory architecture
- **M4 Optimizations** - Special recognition for M4's next-gen Neural Engine

### Model Selection UI
- **Live Download Progress** - Real-time terminal output and progress bars
- **Model Categorization** - Organized by size (Small/3B/7B/13B)
- **Visual Status Indicators** - ✅ installed, ⬇️ needs download
- **Smart Recommendations** - Based on available RAM and hardware
- **MLX Status Display** - Shows if MLX is available for enhanced performance

## Recent Major Changes (v2.3.0)

### Critical Fixes
- **Embedding Dimension Mismatch** - Fixed! Automatically handles switching between models with different dimensions
- **Quick Questions** - Fixed! Now immediately trigger LLM processing
- **Vector Store Management** - Adds metadata tracking and automatic recreation when needed
- **Clear Cache Button** - Manual option to clear vector store

## Recent Major Changes (v2.2.0)

### Model Intelligence
- **Hardware Detection** - Automatically detects RAM, CPU, GPU capabilities
- **Smart Model Selection** - Recommends best models for your hardware
- **Model Customization UI** - Change models on the fly from the sidebar
- **Optimized for Performance** - Uses quantized models (Q4_K_M) for best speed/quality
- **Apple Silicon Support** - Special optimizations for M1/M2/M3 chips

### UI Improvements  
- **Quick Questions** - Now in the main chat area for easy access
- **Better Colors** - Restored nicer color scheme (not all black)
- **Lazy Loading** - Faster startup with deferred imports
- **Model Settings Panel** - Configure AI models from the UI

### Installation
- **Auto Model Download** - Downloads appropriate models based on hardware
- **Windows RAM Detection** - Uses wmic for accurate memory detection
- **Fallback Models** - Ensures compatibility with minimal requirements

## Recent Major Changes (v2.1.0)

- **One-click installation** - `start.sh`/`start.bat` handles EVERYTHING
- **Professional dark theme** - Modern UI with animations and hover effects
- **Removed CLI interface** - Now 100% web-based with Streamlit
- **No sample data** - Users provide their own CSV/Google Sheets
- **Smart installation** - Guides users through missing dependencies

When making changes:
- Primary focus is the Streamlit UI (`app.py`)
- Ensure compatibility with Docker deployment
- Test with sample data for demo scenarios
- Keep UI professional and user-friendly