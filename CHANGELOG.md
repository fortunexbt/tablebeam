# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased] - 2025-07-09

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