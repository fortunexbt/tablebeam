# 🧠 Client Tracker Q&A Assistant

This is a terminal-based assistant that uses [LangChain](https://www.langchain.com/) and [Ollama](https://ollama.com/) to answer natural language questions about institutional validators, onboarding progress, assets, and more.

It loads client data from a CSV file, stores embeddings using ChromaDB, and responds to your queries using a local LLM (`llama3.2` via Ollama).

---

## 🚀 Features

- Semantic search over structured client records
- Embedded using `mxbai-embed-large` via Ollama
- Local LLM Q&A with `llama3.2`
- Terminal interface with color-highlighted prompts
- Easily extensible to web or chatbot frontends

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

Make sure your `client_tracking.csv` file is in the project root, then start the assistant:

```bash
python chat_interface.py
```

You'll see a prompt like:

```
Ask your question about a validator/client (q to quit):
```

---

## 💬 Sample Questions

Try asking:

* `What onboarding steps are still pending for Meria?`
* `Which clients have AUM greater than $1 billion?`
* `Who did Lorenzo speak with in Dubai?`
* `What is the current status of Globalstake's Fireblocks integration?`
* `Summarize all updates for Chorus One.`
* `Which clients are using DFNS?`

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
