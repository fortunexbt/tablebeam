# 📊 Spreadsheet Q&A Assistant

Ask questions about your spreadsheet data in plain English. Get instant AI-powered answers. **100% private** - runs entirely on your computer.

![Demo](https://img.shields.io/badge/Demo-Watch%20Video-red)
![Status](https://img.shields.io/badge/Status-Ready-green)
![License](https://img.shields.io/badge/License-MIT-blue)

## 🚀 Quick Start (2 minutes)

### macOS/Linux:
```bash
git clone https://github.com/yourusername/client-tracker-assistant.git
cd client-tracker-assistant
./start.sh
```

### Windows:
```cmd
git clone https://github.com/yourusername/client-tracker-assistant.git
cd client-tracker-assistant
start.bat
```

**That's it!** The app will:
- ✅ Check all requirements
- ✅ Install everything needed
- ✅ Download AI models (first time only)
- ✅ Open in your browser automatically

## 🎯 What You Can Do

Upload any CSV or connect Google Sheets, then ask questions like:
- "What are the main trends in this data?"
- "Show me the top 10 entries by revenue"
- "Which categories have the most items?"
- "Summarize the key insights"
- "Find all records from last month"

## 📸 Screenshots

### Beautiful Dark Theme UI
The app features a modern, professional interface:
- 🌙 Dark theme that's easy on the eyes
- 📊 Clean data visualization
- 💬 Chat-style interaction
- 🚀 LOCAL/CLOUD mode toggle (cloud coming soon)

### Smart Features
- **Drag & Drop**: Just drop your CSV file
- **Google Sheets**: Paste URL and connect instantly  
- **Natural Language**: No SQL or coding required
- **Privacy First**: Your data never leaves your computer

## 🛠 Requirements

The start script checks and helps install everything:
- **Python 3.9+** (guides you if missing)
- **Ollama** (guides you if missing)
- **10GB disk space** (for AI models)
- **8GB RAM** (16GB recommended)

## 🆘 Troubleshooting

### "Python not found"
- **Windows**: Download from [python.org](https://python.org) - CHECK "Add to PATH"!
- **Mac**: Usually pre-installed, or use `brew install python3`
- **Linux**: Use `sudo apt install python3` or equivalent

### "Ollama not found"
The script will guide you, but:
- **Mac**: [Download Ollama for Mac](https://ollama.com/download/mac)
- **Windows**: [Download Ollama for Windows](https://ollama.com/download/windows)
- **Linux**: Run `curl -fsSL https://ollama.com/install.sh | sh`

### "Port 8501 in use"
Another app is using the port. Either:
- Close other Streamlit apps, OR
- Edit `start.sh` and change `8501` to `8502`

### Still having issues?
1. Make sure you're in the project folder
2. Try deleting `venv/` folder and run again
3. Check you have 10GB free disk space

## 🔮 Roadmap

### Now (Local Mode)
- ✅ CSV file upload
- ✅ Google Sheets connection
- ✅ Natural language Q&A
- ✅ 100% private & local

### Coming Soon (Cloud Mode)
- ⚡ 10x faster with GPU processing
- 👥 Team collaboration
- 💾 Save and share insights
- 🔌 API for integrations
- 📱 Mobile app

## 💡 Pro Tips

1. **First time?** The AI model download takes 5-10 minutes (one time only)
2. **Google Sheets**: Must be "viewable by anyone with link"
3. **Large files**: Start with a smaller sample first
4. **Best results**: Ask specific questions about your data

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

MIT License - use freely for any purpose.

---

**Built with ❤️ by the community** | [Report Issues](https://github.com/yourusername/client-tracker-assistant/issues)