# 📊 Spreadsheet Q&A Assistant

Ask questions about your data in plain English. Get instant AI-powered answers.  
**100% private** - runs entirely on your computer.

## 🚀 Quick Start

```bash
git clone https://github.com/smokingfive/client-tracker-assistant.git
cd client-tracker-assistant
./start.sh        # macOS/Linux
start.bat         # Windows
```

The installer handles everything automatically. Just run and go! ✨

## 💬 What Can You Ask?

Upload any CSV or paste a Google Sheets URL, then ask:
- *"What are the main trends in this data?"*
- *"Show me the top 10 entries by revenue"*
- *"Which categories have the most items?"*
- *"Summarize the key insights"*
- *"Find all records from last month"*

## ✨ Features

### Smart & Simple
- **Auto-loads data** - Just upload or paste URL
- **Natural language** - No SQL or coding required  
- **Quick questions** - One-click common queries
- **Dark theme** - Professional, easy on the eyes

### Powerful AI
- **Hardware detection** - Optimizes for your system
- **Apple Silicon ready** - M1/M2/M3/M4 optimization
- **Smart recommendations** - Best models for your RAM
- **Offline capable** - Everything runs locally

## 💻 System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 4GB | 8GB+ |
| Storage | 10GB | 20GB |
| Python | 3.9+ | 3.11+ |
| OS | Windows/Mac/Linux | Any |

The installer checks and guides you through everything needed.

## 🛠️ Troubleshooting

<details>
<summary><strong>Common Issues</strong></summary>

### "Ollama not found"
- **Mac**: Download from [ollama.com](https://ollama.com/download/mac)
- **Windows**: Download from [ollama.com](https://ollama.com/download/windows)  
- **Linux**: `curl -fsSL https://ollama.com/install.sh | sh`

### "Port 8501 in use"
Another app is using the port. Close other Streamlit apps or change the port in start.sh

### Google Sheets not loading
Make sure your sheet is set to "Anyone with link can view"

### Out of memory
Use the Model Settings panel to select smaller models
</details>

## 🚀 Coming Soon

- ⚡ Cloud mode with GPU acceleration
- 👥 Team collaboration features
- 📱 Mobile app
- 🔌 REST API

## 📄 License

MIT License - free for any use.

---
**Built with Streamlit, LangChain, and Ollama**