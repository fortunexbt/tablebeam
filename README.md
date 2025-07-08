# 🧠 Spreadsheet Q&A Assistant

This is a terminal-based assistant that uses [LangChain](https://www.langchain.com/) and [Ollama](https://ollama.com/) to answer natural language questions about ANY spreadsheet or CSV file.

It loads data from CSV files or Google Sheets, stores embeddings using ChromaDB, and responds to your queries using a local LLM (`llama3.2` via Ollama). Works with any data structure - client lists, inventory, financial data, or any tabular information!

---

## 🚀 Features

- Works with **ANY spreadsheet structure** - no specific columns required
- Load data from local CSV files or Google Sheets URLs
- Semantic search over your data using `mxbai-embed-large` embeddings
- Local LLM Q&A with `llama3.2` - no API keys needed
- Automatically adapts to your column names and data structure
- Terminal interface with color-highlighted prompts
- Privacy-first: all processing happens locally

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
pip install -r requirements.txt
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

## 🧪 Run the Assistant

You can now load data from either a local CSV file or a Google Sheet!

### Option 1: Using a Local CSV File

Make sure your `client_tracking.csv` file is in the project root:

```bash
python chat_interface.py
```

### Option 2: Using Google Sheets

You can provide a Google Sheets URL in three ways:

1. **As a command line argument:**
```bash
python chat_interface.py "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit"
```

2. **Via environment variable:**
```bash
export CLIENT_DATA_SOURCE="https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit"
python chat_interface.py
```

3. **Interactively when prompted:**
```bash
python chat_interface.py
# Then enter the URL when asked
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

## 📝 Project Structure

```bash
.
├── chat_interface.py       # Terminal UI for asking questions
├── vector.py               # Vector DB loading and retriever setup
├── client_tracking.csv     # Source data file
├── requirements.txt        # Python dependencies
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

## 📌 Notes

* Vector data is stored in `./chroma_db_clients/`. Delete to rebuild from scratch.
* "Client" field is highlighted in yellow in terminal output.
* Embeddings exclude terminal color codes for accuracy.

---

## 📞 Support

If you have questions or want to extend this project, feel free to open an issue or contribute via PR. @raj panesar

---
