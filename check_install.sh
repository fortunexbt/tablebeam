#!/bin/bash

# Quick installation check script

echo "🔍 Installation Status Check"
echo "=========================="
echo

# Check Python
echo -n "Python: "
if command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then
    python3 --version 2>/dev/null || python --version
else
    echo "❌ NOT INSTALLED"
fi

# Check pip
echo -n "Pip: "
if command -v pip >/dev/null 2>&1; then
    echo "✅ $(pip --version | cut -d' ' -f2)"
else
    echo "❌ NOT INSTALLED"
fi

# Check virtual environment
echo -n "Virtual Environment: "
if [ -d "venv" ]; then
    echo "✅ EXISTS"
else
    echo "❌ NOT CREATED"
fi

# Check Ollama
echo -n "Ollama: "
if command -v ollama >/dev/null 2>&1; then
    echo "✅ INSTALLED"
    
    # Check if running
    echo -n "Ollama Service: "
    if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        echo "✅ RUNNING"
    else
        echo "⚠️  NOT RUNNING (run 'ollama serve')"
    fi
    
    # Check models
    echo
    echo "AI Models:"
    if ollama list | grep -q "llama3.2"; then
        echo "  - llama3.2: ✅ INSTALLED"
    else
        echo "  - llama3.2: ❌ NOT INSTALLED (~2GB download needed)"
    fi
    
    if ollama list | grep -q "mxbai-embed-large"; then
        echo "  - mxbai-embed-large: ✅ INSTALLED"
    else
        echo "  - mxbai-embed-large: ❌ NOT INSTALLED (~400MB download needed)"
    fi
else
    echo "❌ NOT INSTALLED"
fi

# Check key Python packages
echo
echo "Key Python Packages:"
if [ -d "venv" ] && [ -f "venv/bin/activate" ]; then
    source venv/bin/activate 2>/dev/null
    
    # Check streamlit
    echo -n "  - Streamlit: "
    if pip show streamlit >/dev/null 2>&1; then
        echo "✅ $(pip show streamlit | grep Version | cut -d' ' -f2)"
    else
        echo "❌ NOT INSTALLED"
    fi
    
    # Check langchain
    echo -n "  - LangChain: "
    if pip show langchain >/dev/null 2>&1; then
        echo "✅ $(pip show langchain | grep Version | cut -d' ' -f2)"
    else
        echo "❌ NOT INSTALLED"
    fi
    
    # Check chromadb
    echo -n "  - ChromaDB: "
    if pip show chromadb >/dev/null 2>&1; then
        echo "✅ $(pip show chromadb | grep Version | cut -d' ' -f2)"
    else
        echo "❌ NOT INSTALLED"
    fi
else
    echo "  ⚠️  Cannot check - virtual environment not activated"
fi

echo
echo "=========================="
echo
echo "If any items show ❌, run ./start.sh to install them."
echo