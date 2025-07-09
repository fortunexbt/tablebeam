# 🧠 Spreadsheet Q&A Assistant

A versatile assistant that uses [LangChain](https://www.langchain.com/) and [Ollama](https://ollama.com/) to answer natural language questions about ANY spreadsheet or CSV file. Available as both a local terminal application and a cloud-ready API service.

It loads data from CSV files or Google Sheets, stores embeddings using ChromaDB or Pinecone, and responds to your queries using a local LLM (`llama3.2` via Ollama). Works with any data structure - client lists, inventory, financial data, or any tabular information!

---

## 🚀 Features

### Core Features
- Works with **ANY spreadsheet structure** - no specific columns required
- Load data from local CSV files or Google Sheets URLs
- Semantic search over your data using `mxbai-embed-large` embeddings
- Local LLM Q&A with `llama3.2` - no API keys needed
- Automatically adapts to your column names and data structure
- Terminal interface with color-highlighted prompts
- Privacy-first: all processing happens locally (in local mode)

### New Cloud Features
- **REST API Server**: Deploy as a scalable web service with FastAPI
- **Kubernetes Ready**: Full K8s deployment configs with ArgoCD support
- **Pinecone Integration**: Optional cloud vector store for production deployments
- **Docker Support**: Containerized deployment with multi-stage builds
- **GitHub Actions**: Automated CI/CD pipeline

---

## 📦 Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-org/client-tracker-assistant.git
cd client-tracker-assistant
````

### 2. Install Python dependencies

Make sure you have Python 3.9+ installed, then run:

```bash
pip install -r src/requirements.txt
```

### 3. Install and configure Ollama

#### 🔧 Step-by-step:

1. **Install Ollama** from [https://ollama.com/download](https://ollama.com/download)

   * macOS: via `.dmg` or `brew install ollama`
   * Linux: run the official install script
   * Windows: via `.exe` installer

2. **Verify installation**:

   ```bash
   ollama --version
   ```

3. **Pull required models**:

   These may take a few minutes to download:

   ```bash
   ollama pull llama3.2
   ollama pull mxbai-embed-large
   ```

---

## 🧪 Usage

### Local Mode (Terminal Interface)

The original simple way to use the assistant - perfect for personal use and data privacy.

### Option 1: Using a Local CSV File

Make sure your `client_tracking.csv` file is in the project root:

```bash
python src/chat_interface.py
```

### Option 2: Using Google Sheets

You can provide a Google Sheets URL in three ways:

1. **As a command line argument:**
```bash
python src/chat_interface.py "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit"
```

2. **Via environment variable:**
```bash
export CLIENT_DATA_SOURCE="https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit"
python src/chat_interface.py
```

3. **Interactively when prompted:**
```bash
python src/chat_interface.py
# Then enter the URL when asked
```

### Clearing Previous Data

When switching between different data sources, you can clear the previous vector store:

1. **Using command line flags:**
```bash
# Clear all existing data before loading
python src/chat_interface.py --clear

# Force refresh with new data (keeps old data but adds new)
python src/chat_interface.py --force-refresh

# Both work with data source arguments
python src/chat_interface.py "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit" --clear
```

2. **Interactively when prompted:**
   - When running without arguments, you'll be asked if you want to clear existing data

3. **Manually delete the vector store:**
```bash
rm -rf ./chroma_db_clients/
```

**Important**: Your Google Sheet must be publicly accessible (view-only is fine):
- In Google Sheets: Share → Change to "Anyone with the link can view"

### Supported Google Sheets Formats

- Full URL: `https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit`
- With specific sheet/tab: `https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit#gid=123`
- Just the ID: `1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms`

You'll see a prompt like:

```
Ask your question about a validator/client (q to quit):
```

---

## 💬 Sample Questions

The assistant adapts to your data! Here are some example questions based on different data types:

**For client/customer data:**
* `Which clients are in California?`
* `What's the total revenue from enterprise customers?`
* `Show me all pending orders`

**For inventory/product data:**
* `Which products are low in stock?`
* `What's the average price of items in category X?`
* `List all products from supplier Y`

**For any spreadsheet:**
* `Summarize the data in this spreadsheet`
* `What patterns do you see in the data?`
* `Find all records where [column] contains [value]`

---

### Cloud Mode (API Server)

Deploy as a production-ready API service:

1. **Run with default settings (ChromaDB):**
```bash
python src/api_server.py
```

2. **Run with Pinecone (requires API key):**
```bash
export PINECONE_API_KEY="your-api-key"
export VECTOR_STORE_TYPE="pinecone"
python src/api_server.py
```

3. **Deploy with Docker:**
```bash
docker build -t spreadsheet-qa .
docker run -p 8000:8000 spreadsheet-qa
```

4. **Deploy on Kubernetes:**
```bash
kubectl apply -k k8s/overlays/production/
```

See [Kubernetes Deployment Guide](docs/deployment/kubernetes.md) for full cloud deployment instructions.

---

## 📝 Project Structure

```bash
.
├── src/
│   ├── chat_interface.py       # Terminal UI for local use
│   ├── api_server.py          # FastAPI server for cloud deployment
│   ├── vector.py              # Vector store abstraction (ChromaDB/Pinecone)
│   ├── gsheet_loader.py       # Google Sheets integration
│   ├── pinecone_vector.py     # Pinecone-specific implementation
│   └── requirements.txt       # Python dependencies
├── k8s/                       # Kubernetes deployment configs
├── argocd/                    # ArgoCD GitOps configs
├── .github/workflows/         # CI/CD pipelines
├── Dockerfile                 # Container image definition
├── docs/                      # Documentation
│   ├── deployment/           # Deployment guides
│   └── guides/              # User guides
└── README.md
```

---

## 📋 Requirements File (`requirements.txt`)

```text
langchain
langchain-ollama
langchain-chroma
pandas
colorama
```

---

## 📖 Additional Documentation

### Deployment Guides
- [Kubernetes Deployment](docs/deployment/kubernetes.md) - Full K8s deployment with GPU support
- [ArgoCD GitOps](docs/deployment/argocd.md) - Automated deployment with ArgoCD

### User Guides  
- [Google Sheets Integration](docs/guides/google-sheets.md) - Detailed Google Sheets setup
- [Local vs Cloud Mode](docs/guides/local-vs-cloud.md) - Choosing the right deployment

---

## 🔀 Choosing Between Local and Cloud Mode

### Use Local Mode When:
- Working with sensitive data that must stay on your machine
- Personal use or small teams
- You want the simplest setup with no infrastructure
- Privacy is paramount

### Use Cloud Mode When:
- Building a production application
- Need to serve multiple users concurrently
- Want to integrate with other services via API
- Need scalable vector storage (Pinecone)
- Deploying to Kubernetes/cloud platforms

---

## 📌 Notes

* **Local Mode**: Vector data is stored in `./chroma_db_clients/`. Delete to rebuild from scratch.
* **Cloud Mode**: Can use either ChromaDB (local storage) or Pinecone (cloud storage).
* The first column or common identifier fields are highlighted in yellow in terminal output.
* Embeddings exclude terminal color codes for accuracy.
* Use `--clear` flag to start fresh when switching between different data sources.
* Use `--force-refresh` to update the vector store with new data while keeping existing embeddings.
* All features work with ANY spreadsheet structure - the system adapts to your column names.

---

## 📞 Support

If you have questions or want to extend this project, feel free to open an issue or contribute via PR. @raj panesar

---
