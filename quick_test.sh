#!/bin/bash

# Quick test script for hardware detection

echo "🔍 Quick Hardware Detection Test"
echo "================================"
echo

# Check if Apple Silicon
echo "📱 Checking for Apple Silicon..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    CHIP_STRING=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo "")
    if echo "$CHIP_STRING" | grep -q "Apple"; then
        echo "✅ Apple Silicon detected!"
        echo "   Chip: $CHIP_STRING"
        
        # Extract specific model
        for chip in "M3 Max" "M3 Pro" "M3" "M2 Ultra" "M2 Max" "M2 Pro" "M2" "M1 Ultra" "M1 Max" "M1 Pro" "M1"; do
            if echo "$CHIP_STRING" | grep -q "$chip"; then
                echo "   Model: $chip"
                break
            fi
        done
    else
        echo "❌ Not Apple Silicon (Intel Mac)"
    fi
else
    echo "❌ Not running on macOS"
fi
echo

# Check RAM
echo "💾 Checking RAM..."
if command -v python3 >/dev/null 2>&1; then
    TOTAL_RAM=$(python3 -c "import os; print(f'{os.sysconf(\"SC_PAGE_SIZE\") * os.sysconf(\"SC_PHYS_PAGES\") / (1024**3):.1f}')" 2>/dev/null || echo "Unknown")
    echo "   Total RAM: ${TOTAL_RAM}GB"
else
    echo "   ⚠️  Python3 not found - can't check RAM"
fi
echo

# Check Ollama
echo "🤖 Checking Ollama..."
if command -v ollama >/dev/null 2>&1; then
    echo "✅ Ollama is installed"
    
    # Check if running
    if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        echo "✅ Ollama is running"
        
        # List models
        echo "   Installed models:"
        ollama list 2>/dev/null | tail -n +2 | awk '{print "   - " $1}' | head -5
    else
        echo "❌ Ollama is not running (run: ollama serve)"
    fi
else
    echo "❌ Ollama is not installed"
fi
echo

# Check MLX
echo "🎯 Checking MLX..."
if python3 -c "import mlx" 2>/dev/null; then
    echo "✅ MLX is installed"
else
    echo "❌ MLX not installed (optional - run: pip install mlx-lm)"
fi
echo

# Recommendations
echo "📊 Model Recommendations"
echo "========================"
if [[ "$TOTAL_RAM" != "Unknown" ]]; then
    RAM_GB=${TOTAL_RAM%.*}
    if [ "$RAM_GB" -lt 4 ]; then
        echo "   Low RAM detected - Recommended:"
        echo "   - Embedding: all-minilm"
        echo "   - LLM: phi3:mini"
    elif [ "$RAM_GB" -lt 8 ]; then
        echo "   Moderate RAM detected - Recommended:"
        echo "   - Embedding: nomic-embed-text"
        echo "   - LLM: llama3.2:3b-instruct-q4_K_M"
    else
        echo "   Good RAM detected - Recommended:"
        echo "   - Embedding: mxbai-embed-large"
        echo "   - LLM: mistral:7b-instruct-q4_K_M"
    fi
    
    if echo "$CHIP_STRING" | grep -q "Apple"; then
        echo "   ✨ All models will use Metal GPU acceleration!"
    fi
fi
echo

echo "To start the app, run: ./start.sh"