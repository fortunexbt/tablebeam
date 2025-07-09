# 🧠 Spreadsheet Q&A Assistant

Ask questions about your data in plain English. Works with any CSV file or Google Sheet.

## What is this?

A privacy-first tool that lets you chat with your spreadsheet data using natural language. It runs entirely on your computer using local AI models - no data is sent to the cloud.

**Example questions you can ask:**
- "Which clients are in California?"
- "What's the total revenue by product category?"
- "Show me all pending orders from last month"
- "Summarize the patterns in this data"

## Quick Start

### Prerequisites
- Python 3.9+
- [Ollama](https://ollama.com/download) (free local AI runtime)

### Installation

```bash
# 1. Clone and enter the project
git clone https://github.com/smokingfive/client-tracker-assistant.git
cd client-tracker-assistant

# 2. Install dependencies
pip install -r src/requirements.txt

# 3. Download AI models (one-time setup, ~2GB)
ollama pull llama3.2
ollama pull mxbai-embed-large
```

### Basic Usage

```bash
# Interactive mode (prompts for data source)
python src/chat_interface.py

# With a CSV file
python src/chat_interface.py data.csv

# With Google Sheets
python src/chat_interface.py "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit"
```

That's it! The assistant will load your data and you can start asking questions.

## Features

✅ **Universal** - Works with ANY spreadsheet structure  
✅ **Private** - Everything runs locally on your machine  
✅ **Smart** - Uses semantic search to understand your questions  
✅ **Flexible** - Accepts CSV files or Google Sheets URLs  
✅ **Simple** - No API keys or cloud accounts needed  

## Data Sources

### Local CSV Files
Drop any CSV file in the project folder or provide the path:
```bash
python src/chat_interface.py path/to/your/data.csv
```

### Google Sheets
Make your sheet viewable by anyone with the link, then:
```bash
python src/chat_interface.py "YOUR_GOOGLE_SHEETS_URL"
```

Supported formats:
- Full URL: `https://docs.google.com/spreadsheets/d/abc123/edit`
- Just the ID: `abc123`
- With specific tab: `https://docs.google.com/spreadsheets/d/abc123/edit#gid=0`

## Command Line Options

```bash
# Clear previous data and start fresh
python src/chat_interface.py --clear

# Refresh data while keeping existing embeddings
python src/chat_interface.py --force-refresh

# Combine with data source
python src/chat_interface.py data.csv --clear
```

## Advanced Usage

### API Server Mode

For production deployments or integrations:

```bash
# Run as REST API
python src/api_server.py

# With Docker
docker build -t spreadsheet-qa .
docker run -p 8000:8000 spreadsheet-qa
```

See [deployment docs](docs/deployment/) for Kubernetes and cloud options.

### Environment Variables

```bash
# Set default data source
export CLIENT_DATA_SOURCE="path/to/data.csv"

# Use Pinecone for cloud vector storage (requires API key)
export VECTOR_STORE_TYPE="pinecone"
export PINECONE_API_KEY="your-key"
```

## Documentation

- [Google Sheets Guide](docs/guides/google-sheets.md) - Detailed setup instructions
- [Local vs Cloud Mode](docs/guides/local-vs-cloud.md) - Deployment options
- [Kubernetes Deployment](docs/deployment/kubernetes.md) - Production setup
- [ArgoCD GitOps](docs/deployment/argocd.md) - Automated deployments

## How it Works

1. **Load** - Reads your CSV or Google Sheets data
2. **Index** - Creates semantic embeddings of your data using `mxbai-embed-large`
3. **Search** - Finds relevant records based on your question
4. **Answer** - Uses `llama3.2` to generate natural language responses

All processing happens locally using:
- **Ollama** for running AI models
- **ChromaDB** for vector storage
- **LangChain** for orchestration

## Troubleshooting

**"Ollama not found"**
- Make sure Ollama is installed and running
- Try: `ollama serve` in another terminal

**"Model not found"**  
- Pull the required models: `ollama pull llama3.2`

**"Access denied" with Google Sheets**
- Ensure sheet is set to "Anyone with link can view"

**Out of memory**
- Close other applications
- Try with a smaller dataset first

## What's New 🎉

This project recently merged three major feature branches:
- **Flexible CSV Support** - Now works with ANY data structure
- **Cloud Infrastructure** - Production-ready Kubernetes deployment
- **Generic Spreadsheet Q&A** - Removed client-tracking specific code

See [CHANGELOG.md](CHANGELOG.md) for full details.

## Project Status

This is an actively maintained project that combines:
- The simplicity of a local CLI tool
- The scalability of cloud deployment options
- Support for both CSV files and Google Sheets

Check [TODO.md](TODO.md) for planned features and ways to contribute.
