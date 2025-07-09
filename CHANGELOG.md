# Changelog

All notable changes to this project will be documented in this file.

## [2.1.0] - 2025-07-09

### 🎨 Professional UI Refinement & One-Click Installation

Building on v2.0.0, this release delivers a stunning dark-themed UI and the ultimate simplified installation experience.

### Added
- **One-Click Installation**
  - `start.sh` (macOS/Linux) - Single command does EVERYTHING
  - `start.bat` (Windows) - Single command does EVERYTHING
  - Automatic dependency installation
  - Built-in Ollama checker and guide
  - Automatic model downloads
  - Beautiful progress indicators
- **Professional Dark Theme UI**
  - Modern dark color scheme (#0e1117 base)
  - Animated hover effects
  - Card-based layout
  - Professional status indicators
  - Improved chat interface
  - Better error handling with troubleshooting guides
- **Enhanced User Experience**
  - Cleaner welcome screen with feature cards
  - Step-by-step getting started guide
  - Available models display in sidebar
  - File size indicator for uploads
  - Limited source data display (top 3 only)

### Changed
- **Installation Process** - Now literally one command: `./start.sh` or `start.bat`
- **UI Theme** - From default to professional dark theme
- **Documentation** - Simplified to focus on the one-click experience
- **Sample Questions** - More intuitive and data-agnostic

### Removed
- Old `install.sh` and `run.sh` (replaced by `start.sh`)
- Complex installation instructions
- Sample data references from UI

## [2.0.0] - 2025-07-09

### 🎉 Major UI Overhaul - Web Interface Launch

This release transforms the project from a command-line tool to a beautiful web application with a focus on executive-friendly demos and simplified installation.

### Added
- **Streamlit Web UI** (`src/app.py`) - Professional web interface replacing CLI
  - Drag-and-drop CSV upload
  - Google Sheets URL input
  - Chat-style Q&A interface
  - Sample data pre-loaded for demos
  - LOCAL vs CLOUD mode toggle (cloud coming soon)
  - Real-time Ollama status indicator
- **One-Click Installation**
  - `install.sh` for macOS/Linux - automated setup script
  - `install.bat` for Windows - automated setup script
  - Virtual environment creation
  - Automatic model downloads
  - `run.sh`/`run.bat` for easy startup
- **Sample Data** - 15 companies dataset for immediate demos
- **Executive-Friendly Documentation** - Simplified README focused on business value

### Changed
- **Primary Interface** - Streamlit web app is now the main interface
- **Installation Process** - Reduced from multiple steps to single script
- **Documentation** - Complete rewrite focusing on simplicity and demo readiness
- **Architecture** - Maintained cloud infrastructure for future deployment
- **User Experience** - From developer-focused CLI to business-ready web app

### Removed
- `chat_interface.py` - CLI interface (replaced by web UI)
- Complex Docker deployment for demos (kept infrastructure for future)
- Technical jargon from main documentation
- Pinecone from default requirements (kept code for future)

### Developer Notes
- Cloud infrastructure preserved in k8s/, argocd/ directories
- API server (`api_server.py`) maintained for future integrations
- Pinecone integration code retained but not active by default
- All changes focused on demo-ability while preserving scalability

## [1.1.0] - 2025-07-09

### Added
- **Google Sheets Integration** - Load data directly from Google Sheets URLs without downloading
- **Flexible Data Support** - Now works with ANY spreadsheet structure, not just client tracking
- **Cloud Deployment** - Full production-ready deployment with:
  - FastAPI REST API server
  - Docker containerization  
  - Kubernetes manifests with GPU support
  - ArgoCD GitOps configuration
  - GitHub Actions CI/CD pipeline
- **Pinecone Vector Store** - Optional cloud vector storage for production scale
- **API Mode** - Run as a REST API service for integrations
- **Improved Data Loading**:
  - `--clear` flag to reset vector store
  - `--force-refresh` flag to update embeddings
  - Support for Google Sheets ID, full URL, or tab-specific URLs
- **Better Documentation Structure** - Organized docs/ directory with deployment and user guides

### Changed
- Reorganized codebase - all source files now in `src/` directory
- Updated vector store to support both ChromaDB (local) and Pinecone (cloud)
- Enhanced data processing to adapt to any column structure
- Improved terminal output with better formatting
- README rewritten for clarity and better onboarding

### Fixed
- File path issues in documentation
- Import errors with relative paths
- Memory efficiency improvements

### Removed
- GitHub Actions workflow (was failing)
- Development artifacts and test files
- Scattered documentation files (consolidated to docs/)
- Hard-coded client tracking assumptions

## [1.0.0] - 2024-12-06

### Initial Release
- Basic Q&A functionality for CSV files
- ChromaDB vector storage
- Ollama integration with llama3.2
- Terminal chat interface
- Client tracking focus